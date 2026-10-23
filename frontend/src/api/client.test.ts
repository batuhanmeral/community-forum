import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import axios, { AxiosError, type AxiosAdapter, type AxiosResponse } from 'axios';
import { api } from './client';
import { store } from '@/app/store';
import { SESSION_KEY, logout, sessionChanged, setAccessToken } from '@/features/auth/authSlice';
import { fakeJwt } from '@/test/fakeJwt';

const adapter = vi.fn<AxiosAdapter>();
const A1 = fakeJwt({ user_id: 7, jti: 'a1' });
const A3 = fakeJwt({ user_id: 7, jti: 'a3' });

function httpError(status: number) {
  return new AxiosError('failed', 'ERR_BAD_REQUEST', undefined, null, {
    status,
    statusText: '',
    data: {},
    headers: {},
  } as AxiosResponse);
}

function refreshFails(status: number | 'network') {
  const err = status === 'network' ? new AxiosError('Network Error', 'ERR_NETWORK') : httpError(status);
  vi.spyOn(axios, 'post').mockRejectedValue(err);
}

function refreshSucceeds(access: string) {
  vi.spyOn(axios, 'post').mockResolvedValue({ data: { access } });
}

function lastAuthHeader() {
  return adapter.mock.calls.at(-1)?.[0].headers.Authorization;
}

function ok(config: Parameters<AxiosAdapter>[0]) {
  return Promise.resolve({ data: {}, status: 200, statusText: 'OK', headers: {}, config });
}

describe('api client token refresh', () => {
  beforeEach(() => {
    localStorage.clear();
    store.dispatch(setAccessToken(A1));
    adapter.mockReset();
    // First attempt is rejected as expired, the retry succeeds.
    adapter.mockImplementationOnce(async (config) => {
      throw new AxiosError('unauthorized', 'ERR_BAD_REQUEST', config, null, {
        status: 401,
        statusText: 'Unauthorized',
        data: {},
        headers: {},
        config,
      });
    });
    adapter.mockImplementation(ok);
    api.defaults.adapter = adapter;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('sends credentials so the refresh cookie travels with auth calls', () => {
    expect(api.defaults.withCredentials).toBe(true);
  });

  it('refreshes from the cookie and retries with the new access token', async () => {
    refreshSucceeds(A3);
    await api.get('/x/');
    const [url, body, config] = vi.mocked(axios.post).mock.calls[0];
    expect(url).toMatch(/\/auth\/refresh\/$/);
    expect(body).toBeNull();
    expect(config?.withCredentials).toBe(true);
    expect(lastAuthHeader()).toBe(`Bearer ${A3}`);
    expect(localStorage.getItem('nexus.refresh')).toBeNull();
  });

  it('keeps the session when refresh returns 429', async () => {
    refreshFails(429);
    await expect(api.get('/x/')).rejects.toBeTruthy();
    expect(store.getState().auth.sessionUserId).toBe('7');
    expect(localStorage.getItem(SESSION_KEY)).toBe('7');
  });

  it('keeps the session on a network error', async () => {
    refreshFails('network');
    await expect(api.get('/x/')).rejects.toBeTruthy();
    expect(store.getState().auth.sessionUserId).toBe('7');
  });

  it.each([400, 401])('logs out when refresh rejects the token with %i', async (status) => {
    refreshFails(status);
    await expect(api.get('/x/')).rejects.toBeTruthy();
    expect(store.getState().auth.sessionUserId).toBeNull();
    expect(localStorage.getItem(SESSION_KEY)).toBeNull();
  });

  it('discards a refresh that resolves after a logout', async () => {
    vi.spyOn(axios, 'post').mockImplementation(async () => {
      store.dispatch(logout());
      return { data: { access: A3 } };
    });
    await expect(api.get('/x/')).rejects.toBeTruthy();
    expect(store.getState().auth.accessToken).toBeNull();
    expect(localStorage.getItem(SESSION_KEY)).toBeNull();
  });

  it('logs out without calling refresh when another tab already logged out', async () => {
    localStorage.removeItem(SESSION_KEY);
    refreshSucceeds(A3);
    await expect(api.get('/x/')).rejects.toBeTruthy();
    expect(axios.post).not.toHaveBeenCalled();
    expect(store.getState().auth.sessionUserId).toBeNull();
  });

  it('runs the refresh under the cross-tab lock when the browser has one', async () => {
    const request = vi.fn((_name: string, fn: () => Promise<unknown>) => fn());
    Object.defineProperty(navigator, 'locks', { configurable: true, value: { request } });
    try {
      refreshSucceeds(A3);
      await api.get('/x/');
      expect(request).toHaveBeenCalledWith('nexus.auth.refresh', expect.any(Function));
      expect(lastAuthHeader()).toBe(`Bearer ${A3}`);
    } finally {
      delete (navigator as { locks?: unknown }).locks;
    }
  });

  it('gives up on a hung refresh after 10 seconds and keeps the session', async () => {
    vi.useFakeTimers();
    try {
      // Mirrors axios' adapters: a request with a timeout fails with ECONNABORTED and no response.
      vi.spyOn(axios, 'post').mockImplementation(
        (_url, _data, config) =>
          new Promise((_resolve, reject) => {
            if (config?.timeout) {
              setTimeout(() => reject(new AxiosError('timeout exceeded', 'ECONNABORTED')), config.timeout);
            }
          }),
      );
      const request = api.get('/x/').then(
        () => 'resolved',
        () => 'rejected',
      );
      await vi.advanceTimersByTimeAsync(10_000);
      await expect(Promise.race([request, Promise.resolve('pending')])).resolves.toBe('rejected');
      expect(store.getState().auth.sessionUserId).toBe('7');
    } finally {
      vi.useRealTimers();
    }
  });
});

describe('api client session restore', () => {
  beforeEach(() => {
    localStorage.clear();
    store.dispatch(setAccessToken(A1));
    // A reload, or another tab's account switch: the session exists but this tab has no access token.
    store.dispatch(sessionChanged('7'));
    adapter.mockReset();
    adapter.mockImplementation(ok);
    api.defaults.adapter = adapter;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('restores the access token once before concurrent first requests', async () => {
    refreshSucceeds(A3);
    await Promise.all([api.get('/a/'), api.get('/b/')]);
    expect(axios.post).toHaveBeenCalledTimes(1);
    expect(adapter.mock.calls.map(([c]) => c.headers.Authorization)).toEqual([
      `Bearer ${A3}`,
      `Bearer ${A3}`,
    ]);
  });

  it('sends the request anonymously when the restore fails transiently', async () => {
    refreshFails(503);
    await api.get('/a/');
    expect(lastAuthHeader()).toBeUndefined();
    expect(store.getState().auth.sessionUserId).toBe('7');
  });

  it('does not restore for anonymous visitors', async () => {
    store.dispatch(logout());
    refreshSucceeds(A3);
    await api.get('/a/');
    expect(axios.post).not.toHaveBeenCalled();
  });

  it('never triggers a restore from auth endpoints', async () => {
    refreshSucceeds(A3);
    await api.post('/auth/login/', {});
    expect(axios.post).not.toHaveBeenCalled();
  });
});

describe('api client refresh racing a sign-in elsewhere', () => {
  beforeEach(() => {
    localStorage.clear();
    store.dispatch(setAccessToken(A1));
    store.dispatch(sessionChanged('7'));
    adapter.mockReset();
    adapter.mockImplementation(ok);
    api.defaults.adapter = adapter;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('does not adopt a token when another account signed in during the refresh', async () => {
    vi.spyOn(axios, 'post').mockImplementation(async () => {
      localStorage.setItem(SESSION_KEY, '99');
      return { data: { access: A3 } };
    });
    await api.get('/a/');
    expect(lastAuthHeader()).toBeUndefined();
    expect(localStorage.getItem(SESSION_KEY)).toBe('99');
    expect(store.getState().auth.accessToken).toBeNull();
  });
});

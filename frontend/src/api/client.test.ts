import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import axios, { AxiosError, type AxiosAdapter, type AxiosResponse } from 'axios';
import { api } from './client';
import { store } from '@/app/store';
import { ACCESS_KEY, REFRESH_KEY, logout, setTokens } from '@/features/auth/authSlice';

const adapter = vi.fn<AxiosAdapter>();

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

function refreshSucceeds(data: { access: string; refresh: string }) {
  vi.spyOn(axios, 'post').mockResolvedValue({ data });
}

function refreshFailsAfter(status: number, sideEffect: () => void) {
  vi.spyOn(axios, 'post').mockImplementation(async () => {
    sideEffect();
    throw httpError(status);
  });
}

function lastAuthHeader() {
  return adapter.mock.calls.at(-1)?.[0].headers.Authorization;
}

describe('api client token refresh', () => {
  beforeEach(() => {
    localStorage.clear();
    store.dispatch(setTokens({ access: 'a1', refresh: 'r1' }));
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
    adapter.mockImplementation(async (config) => ({
      data: {},
      status: 200,
      statusText: 'OK',
      headers: {},
      config,
    }));
    api.defaults.adapter = adapter;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('keeps the session when refresh returns 429', async () => {
    refreshFails(429);
    await expect(api.get('/x/')).rejects.toBeTruthy();
    expect(store.getState().auth.refreshToken).toBe('r1');
    expect(localStorage.getItem(REFRESH_KEY)).toBe('r1');
  });

  it('keeps the session on a network error', async () => {
    refreshFails('network');
    await expect(api.get('/x/')).rejects.toBeTruthy();
    expect(store.getState().auth.refreshToken).toBe('r1');
    expect(localStorage.getItem(REFRESH_KEY)).toBe('r1');
  });

  it.each([400, 401])('logs out when refresh rejects the token with %i', async (status) => {
    refreshFails(status);
    await expect(api.get('/x/')).rejects.toBeTruthy();
    expect(store.getState().auth.refreshToken).toBeNull();
    expect(localStorage.getItem(REFRESH_KEY)).toBeNull();
  });

  it('sends the refresh token currently in localStorage', async () => {
    localStorage.setItem(REFRESH_KEY, 'r2'); // another tab rotated; store still has r1
    refreshSucceeds({ access: 'a3', refresh: 'r3' });
    await api.get('/x/');
    expect(vi.mocked(axios.post).mock.calls[0][1]).toEqual({ refresh: 'r2' });
    expect(lastAuthHeader()).toBe('Bearer a3');
  });

  it('adopts tokens rotated by another tab instead of logging out', async () => {
    refreshFailsAfter(401, () => {
      localStorage.setItem(ACCESS_KEY, 'a9');
      localStorage.setItem(REFRESH_KEY, 'r9');
    });
    await api.get('/x/'); // retried with a9 -> 200
    expect(lastAuthHeader()).toBe('Bearer a9');
    expect(store.getState().auth.refreshToken).toBe('r9');
  });

  it('discards a refresh that resolves after a logout', async () => {
    vi.spyOn(axios, 'post').mockImplementation(async () => {
      store.dispatch(logout());
      return { data: { access: 'a3', refresh: 'r3' } };
    });
    await expect(api.get('/x/')).rejects.toBeTruthy();
    expect(localStorage.getItem(ACCESS_KEY)).toBeNull();
    expect(localStorage.getItem(REFRESH_KEY)).toBeNull();
    expect(store.getState().auth.refreshToken).toBeNull();
  });

  it('prefers tokens another tab rotated while this refresh was in flight', async () => {
    vi.spyOn(axios, 'post').mockImplementation(async () => {
      localStorage.setItem(ACCESS_KEY, 'a9');
      localStorage.setItem(REFRESH_KEY, 'r9');
      return { data: { access: 'a3', refresh: 'r3' } };
    });
    await api.get('/x/');
    expect(lastAuthHeader()).toBe('Bearer a9');
    expect(store.getState().auth.refreshToken).toBe('r9');
    expect(localStorage.getItem(REFRESH_KEY)).toBe('r9');
  });

  it('logs out when another tab already removed the refresh token', async () => {
    localStorage.removeItem(REFRESH_KEY);
    refreshSucceeds({ access: 'a3', refresh: 'r3' });
    await expect(api.get('/x/')).rejects.toBeTruthy();
    expect(axios.post).not.toHaveBeenCalled();
    expect(store.getState().auth.refreshToken).toBeNull();
  });

  it('runs the refresh under the cross-tab lock when the browser has one', async () => {
    const request = vi.fn((_name: string, fn: () => Promise<unknown>) => fn());
    Object.defineProperty(navigator, 'locks', { configurable: true, value: { request } });
    try {
      refreshSucceeds({ access: 'a3', refresh: 'r3' });
      await api.get('/x/');
      expect(request).toHaveBeenCalledWith('nexus.auth.refresh', expect.any(Function));
      expect(lastAuthHeader()).toBe('Bearer a3');
    } finally {
      delete (navigator as { locks?: unknown }).locks;
    }
  });

  it('uses the access token another tab already refreshed without calling refresh', async () => {
    localStorage.setItem(ACCESS_KEY, 'a5');
    refreshFails(500);
    await api.get('/x/');
    expect(axios.post).not.toHaveBeenCalled();
    expect(lastAuthHeader()).toBe('Bearer a5');
    expect(store.getState().auth.accessToken).toBe('a5');
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
      expect(store.getState().auth.refreshToken).toBe('r1');
      expect(localStorage.getItem(REFRESH_KEY)).toBe('r1');
    } finally {
      vi.useRealTimers();
    }
  });
});

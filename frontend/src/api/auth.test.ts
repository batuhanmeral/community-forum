import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AxiosError, type AxiosAdapter } from 'axios';
import { api } from './client';
import { login, logoutRequest, retryPendingLogout } from './auth';

describe('logoutRequest', () => {
  const defaultAdapter = api.defaults.adapter;

  afterEach(() => {
    api.defaults.adapter = defaultAdapter;
    vi.useRealTimers();
  });

  // It runs under the cross-tab refresh lock, so a hung request would block every tab's refresh.
  it('gives up on a hung logout request after 10 seconds', async () => {
    vi.useFakeTimers();
    // Mirrors axios' adapters: a request with a timeout fails with ECONNABORTED and no response.
    const hangingAdapter: AxiosAdapter = (config) =>
      new Promise((_resolve, reject) => {
        if (config.timeout) {
          setTimeout(() => reject(new AxiosError('timeout exceeded', 'ECONNABORTED', config)), config.timeout);
        }
      });
    api.defaults.adapter = hangingAdapter;
    const done = logoutRequest().then(() => 'settled');
    await vi.advanceTimersByTimeAsync(10_000);
    await expect(Promise.race([done, Promise.resolve('pending')])).resolves.toBe('settled');
  });
});

describe('pending logout', () => {
  const okAdapter: AxiosAdapter = async (config) => ({ data: {}, status: 204, statusText: '', headers: {}, config });
  const failingAdapter: AxiosAdapter = async (config) => {
    throw new AxiosError('down', 'ERR_NETWORK', config);
  };

  beforeEach(() => localStorage.clear());

  it('remembers a failed logout and finishes it on the next load', async () => {
    api.defaults.adapter = failingAdapter;
    await logoutRequest();
    expect(localStorage.getItem('nexus.logoutPending')).toBe('1');
    const retried = vi.fn(okAdapter);
    api.defaults.adapter = retried;
    await retryPendingLogout();
    expect(retried).toHaveBeenCalledTimes(1);
    expect(localStorage.getItem('nexus.logoutPending')).toBeNull();
  });

  it('does not end a session that started after the failed logout', async () => {
    localStorage.setItem('nexus.logoutPending', '1');
    localStorage.setItem('nexus.session', '7');
    const retried = vi.fn(okAdapter);
    api.defaults.adapter = retried;
    await retryPendingLogout();
    expect(retried).not.toHaveBeenCalled();
  });

  it('clears the pending logout once a new login succeeds', async () => {
    localStorage.setItem('nexus.logoutPending', '1');
    api.defaults.adapter = async (config) => ({ data: { access: 'a' }, status: 200, statusText: '', headers: {}, config });
    await login({ username: 'u', password: 'p' });
    expect(localStorage.getItem('nexus.logoutPending')).toBeNull();
  });
});

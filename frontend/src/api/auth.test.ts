import { afterEach, describe, expect, it, vi } from 'vitest';
import { AxiosError, type AxiosAdapter } from 'axios';
import { api } from './client';
import { logoutRequest } from './auth';

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
    const done = logoutRequest('r1').then(() => 'settled');
    await vi.advanceTimersByTimeAsync(10_000);
    await expect(Promise.race([done, Promise.resolve('pending')])).resolves.toBe('settled');
  });
});

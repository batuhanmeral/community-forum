import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AxiosError, AxiosHeaders } from 'axios';
import { api } from './client';
import { requestRealtimeTicket } from './realtime';

function httpError(status: number) {
  const config = { headers: new AxiosHeaders() };
  return new AxiosError('failed', String(status), config, null, {
    status,
    statusText: '',
    headers: {},
    config,
    data: {},
  });
}

describe('requestRealtimeTicket', () => {
  beforeEach(() => vi.restoreAllMocks());

  it('returns the ticket', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: { ticket: 'tkt', expires_in: 30 } });
    await expect(requestRealtimeTicket()).resolves.toBe('tkt');
    expect(post).toHaveBeenCalledWith('/realtime/ticket/');
  });

  it.each([503, 404])('maps %i to "realtime is off"', async (status) => {
    vi.spyOn(api, 'post').mockRejectedValue(httpError(status));
    await expect(requestRealtimeTicket()).resolves.toBeNull();
  });

  it('rethrows other failures so the client backs off and retries', async () => {
    vi.spyOn(api, 'post').mockRejectedValue(httpError(500));
    await expect(requestRealtimeTicket()).rejects.toBeInstanceOf(AxiosError);
  });
});

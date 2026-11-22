import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  DISABLED_RETRY_MS,
  MAX_BACKOFF_MS,
  PING_MS,
  createRealtimeClient,
  type RealtimeEvent,
} from './realtime';
import { FakeWebSocket, acceptLastSocket } from '@/test/fakeWebSocket';

const URL = 'ws://localhost/ws/v1/stream/';

function setup(fetchTicket = vi.fn<() => Promise<string | null>>().mockResolvedValue('tkt')) {
  const client = createRealtimeClient({
    fetchTicket,
    url: () => URL,
    createSocket: (url) => new FakeWebSocket(url) as unknown as WebSocket,
    // Upper end of the jitter range: delays equal the nominal backoff.
    random: () => 1,
  });
  const events: RealtimeEvent[] = [];
  client.subscribe((event) => events.push(event));
  return { client, fetchTicket, events };
}

const flush = () => vi.advanceTimersByTimeAsync(0);

function setHidden(hidden: boolean) {
  Object.defineProperty(document, 'hidden', { configurable: true, value: hidden });
  document.dispatchEvent(new Event('visibilitychange'));
}

let stopClient: (() => void) | null = null;

beforeEach(() => {
  vi.useFakeTimers();
  FakeWebSocket.reset();
  Object.defineProperty(document, 'hidden', { configurable: true, value: false });
});

afterEach(() => {
  stopClient?.();
  stopClient = null;
  vi.useRealTimers();
});

async function started(fetchTicket?: Parameters<typeof setup>[0]) {
  const ctx = setup(fetchTicket);
  ctx.client.start();
  stopClient = () => ctx.client.stop();
  await flush();
  return ctx;
}

describe('realtime client', () => {
  it('sends a fresh ticket as the first frame, never in the URL', async () => {
    const { client } = await started();
    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(FakeWebSocket.last.url).toBe(URL);
    FakeWebSocket.last.open();
    expect(FakeWebSocket.last.sentJson()).toEqual([{ type: 'auth', ticket: 'tkt' }]);
    expect(client.isConnected()).toBe(false);
  });

  it('reports connected once ready and asks listeners to resync', async () => {
    const { client, events } = await started();
    const onStatus = vi.fn();
    client.subscribeStatus(onStatus);
    acceptLastSocket();
    expect(client.isConnected()).toBe(true);
    expect(onStatus).toHaveBeenCalledTimes(1);
    expect(events).toEqual([{ type: 'resync' }]);
  });

  it('delivers server events and drops pongs and garbage', async () => {
    const { events } = await started();
    acceptLastSocket();
    FakeWebSocket.last.receive({ type: 'message.created', conversation_id: 3 });
    FakeWebSocket.last.receive({ type: 'pong' });
    FakeWebSocket.last.receive('not json');
    FakeWebSocket.last.receive({ no: 'type' });
    expect(events).toEqual([{ type: 'resync' }, { type: 'message.created', conversation_id: 3 }]);
  });

  it('pings while connected', async () => {
    await started();
    acceptLastSocket();
    await vi.advanceTimersByTimeAsync(PING_MS);
    expect(FakeWebSocket.last.sentJson()).toContainEqual({ type: 'ping' });
  });

  it('falls back on a drop and reconnects with a new ticket after a backoff', async () => {
    const { client, fetchTicket } = await started();
    acceptLastSocket();
    FakeWebSocket.last.drop();
    expect(client.isConnected()).toBe(false);
    await vi.advanceTimersByTimeAsync(999);
    expect(fetchTicket).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(fetchTicket).toHaveBeenCalledTimes(2);
    expect(FakeWebSocket.instances).toHaveLength(2);
  });

  it('backs off exponentially up to the cap while the server keeps refusing', async () => {
    const { fetchTicket } = await started();
    for (let i = 0; i < 10; i += 1) {
      FakeWebSocket.last.drop(4001);
      await vi.advanceTimersByTimeAsync(MAX_BACKOFF_MS);
    }
    expect(fetchTicket).toHaveBeenCalledTimes(11);
    FakeWebSocket.last.drop(4001);
    await vi.advanceTimersByTimeAsync(MAX_BACKOFF_MS - 1);
    expect(fetchTicket).toHaveBeenCalledTimes(11);
    await vi.advanceTimersByTimeAsync(1);
    expect(fetchTicket).toHaveBeenCalledTimes(12);
  });

  it('jitters the backoff downwards', async () => {
    const fetchTicket = vi.fn<() => Promise<string | null>>().mockResolvedValue('tkt');
    const client = createRealtimeClient({
      fetchTicket,
      url: () => URL,
      createSocket: (url) => new FakeWebSocket(url) as unknown as WebSocket,
      random: () => 0,
    });
    client.start();
    stopClient = () => client.stop();
    await flush();
    FakeWebSocket.last.drop();
    await vi.advanceTimersByTimeAsync(500);
    expect(fetchTicket).toHaveBeenCalledTimes(2);
  });

  it('retries when the ticket request fails', async () => {
    const fetchTicket = vi
      .fn<() => Promise<string | null>>()
      .mockRejectedValueOnce(new Error('network'))
      .mockResolvedValue('tkt');
    await started(fetchTicket);
    expect(FakeWebSocket.instances).toHaveLength(0);
    await vi.advanceTimersByTimeAsync(1000);
    expect(FakeWebSocket.instances).toHaveLength(1);
  });

  it('only checks back rarely when the server has realtime off', async () => {
    const fetchTicket = vi.fn<() => Promise<string | null>>().mockResolvedValue(null);
    await started(fetchTicket);
    expect(FakeWebSocket.instances).toHaveLength(0);
    setHidden(true);
    setHidden(false);
    await vi.advanceTimersByTimeAsync(DISABLED_RETRY_MS - 1);
    expect(fetchTicket).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(fetchTicket).toHaveBeenCalledTimes(2);
  });

  it('stop closes the socket and cancels reconnects', async () => {
    const { client, fetchTicket } = await started();
    acceptLastSocket();
    const socket = FakeWebSocket.last;
    client.stop();
    expect(socket.closedWith).toBe(1000);
    expect(client.isConnected()).toBe(false);
    socket.drop(1000);
    await vi.advanceTimersByTimeAsync(10 * MAX_BACKOFF_MS);
    expect(fetchTicket).toHaveBeenCalledTimes(1);
  });

  it('ignores a ticket that arrives after stop', async () => {
    let resolve: (ticket: string) => void = () => undefined;
    const fetchTicket = vi.fn(() => new Promise<string | null>((r) => (resolve = r)));
    const { client } = setup(fetchTicket);
    client.start();
    client.stop();
    resolve('late');
    await flush();
    expect(FakeWebSocket.instances).toHaveLength(0);
  });

  it('reconnects at once when the tab becomes visible again', async () => {
    const { fetchTicket } = await started();
    for (let i = 0; i < 4; i += 1) {
      FakeWebSocket.last.drop();
      await vi.advanceTimersByTimeAsync(MAX_BACKOFF_MS);
    }
    FakeWebSocket.last.drop();
    const before = fetchTicket.mock.calls.length;
    setHidden(true);
    setHidden(false);
    await flush();
    expect(fetchTicket).toHaveBeenCalledTimes(before + 1);
  });

  it('resyncs when the tab becomes visible while connected', async () => {
    const { events } = await started();
    acceptLastSocket();
    setHidden(true);
    setHidden(false);
    expect(events).toEqual([{ type: 'resync' }, { type: 'resync' }]);
  });
});

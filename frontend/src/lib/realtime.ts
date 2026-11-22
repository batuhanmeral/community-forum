/**
 * Realtime connection manager: one WebSocket per tab carrying wake-up events
 * ("message.created in conversation 12"). Events carry no content; listeners refetch over REST.
 *
 * Flow: fetch a one-time ticket (JWT-authenticated REST call) → open the socket → send the ticket
 * as the first frame. Drops are retried with exponential backoff and jitter; while disconnected
 * the app keeps polling, so a broken socket only makes updates slower.
 */

/** A server event, or the local "resync" (just (re)connected or back on the tab: refetch once). */
export interface RealtimeEvent {
  type: string;
  conversation_id?: number;
}

export interface RealtimeDeps {
  /** A one-time ticket, or null when the server has realtime turned off. */
  fetchTicket: () => Promise<string | null>;
  url: () => string;
  createSocket: (url: string) => WebSocket;
  random?: () => number;
}

export const PING_MS = 25_000;
export const MAX_BACKOFF_MS = 30_000;
export const DISABLED_RETRY_MS = 5 * 60_000;
const BASE_BACKOFF_MS = 1_000;
const OPEN = 1;

export interface RealtimeClient {
  start(): void;
  stop(): void;
  isConnected(): boolean;
  subscribe(listener: (event: RealtimeEvent) => void): () => void;
  subscribeStatus(listener: () => void): () => void;
}

export function createRealtimeClient(deps: RealtimeDeps): RealtimeClient {
  const random = deps.random ?? Math.random;
  const listeners = new Set<(event: RealtimeEvent) => void>();
  const statusListeners = new Set<() => void>();
  let running = false;
  let connected = false;
  let socket: WebSocket | null = null;
  let attempt = 0;
  let disabled = false;
  // Bumped by every connect and stop, so a late ticket from an older attempt is dropped.
  let generation = 0;
  let retryTimer: ReturnType<typeof setTimeout> | undefined;
  let pingTimer: ReturnType<typeof setInterval> | undefined;

  const emit = (event: RealtimeEvent) => listeners.forEach((listener) => listener(event));

  function setConnected(value: boolean) {
    if (connected === value) return;
    connected = value;
    statusListeners.forEach((listener) => listener());
  }

  function schedule(delayMs: number) {
    clearTimeout(retryTimer);
    retryTimer = setTimeout(() => void connect(), delayMs);
  }

  function nextBackoff(): number {
    const nominal = Math.min(MAX_BACKOFF_MS, BASE_BACKOFF_MS * 2 ** attempt);
    attempt += 1;
    // "Equal jitter": somewhere in the upper half, so tabs don't reconnect in lockstep.
    return nominal / 2 + (random() * nominal) / 2;
  }

  async function connect() {
    if (!running) return;
    const current = ++generation;
    let ticket: string | null;
    try {
      ticket = await deps.fetchTicket();
    } catch {
      if (current === generation && running) schedule(nextBackoff());
      return;
    }
    if (current !== generation || !running) return;
    disabled = ticket === null;
    if (ticket === null) {
      schedule(DISABLED_RETRY_MS);
      return;
    }
    open(ticket);
  }

  function open(ticket: string) {
    const ws = deps.createSocket(deps.url());
    socket = ws;
    // The ticket goes in the first frame, never the URL (which proxies log).
    ws.onopen = () => ws.send(JSON.stringify({ type: 'auth', ticket }));
    ws.onmessage = (message) => {
      if (socket !== ws) return;
      const event = parse(message.data);
      if (!event || event.type === 'pong') return;
      if (event.type === 'ready') {
        attempt = 0;
        startPing(ws);
        setConnected(true);
        emit({ type: 'resync' });
        return;
      }
      emit(event);
    };
    ws.onclose = () => {
      if (socket !== ws) return;
      socket = null;
      clearInterval(pingTimer);
      setConnected(false);
      if (running) schedule(nextBackoff());
    };
  }

  function startPing(ws: WebSocket) {
    clearInterval(pingTimer);
    pingTimer = setInterval(() => {
      if (ws.readyState === OPEN) ws.send(JSON.stringify({ type: 'ping' }));
    }, PING_MS);
  }

  function onVisibilityChange() {
    if (document.hidden || !running) return;
    if (connected) emit({ type: 'resync' });
    // A phone may have slept through the backoff; don't make the user wait it out.
    else if (!socket && !disabled) {
      attempt = 0;
      schedule(0);
    }
  }

  return {
    start() {
      if (running) return;
      running = true;
      attempt = 0;
      disabled = false;
      document.addEventListener('visibilitychange', onVisibilityChange);
      void connect();
    },
    stop() {
      running = false;
      generation += 1;
      clearTimeout(retryTimer);
      clearInterval(pingTimer);
      document.removeEventListener('visibilitychange', onVisibilityChange);
      const ws = socket;
      socket = null;
      ws?.close(1000);
      setConnected(false);
    },
    isConnected: () => connected,
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    subscribeStatus(listener) {
      statusListeners.add(listener);
      return () => statusListeners.delete(listener);
    },
  };
}

function parse(data: unknown): RealtimeEvent | null {
  if (typeof data !== 'string') return null;
  try {
    const value: unknown = JSON.parse(data);
    if (typeof value === 'object' && value !== null && typeof (value as RealtimeEvent).type === 'string') {
      return value as RealtimeEvent;
    }
  } catch {
    // Not JSON: ignore.
  }
  return null;
}

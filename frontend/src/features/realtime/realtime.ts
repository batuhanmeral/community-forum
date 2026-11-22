import { useEffect, useRef, useSyncExternalStore } from 'react';
import type { RootState } from '@/app/store';
import { requestRealtimeTicket } from '@/api/realtime';
import { createRealtimeClient, type RealtimeClient, type RealtimeEvent } from '@/lib/realtime';

export type { RealtimeEvent } from '@/lib/realtime';

/** Same origin by default (nginx, or the Vite proxy in dev, forwards /ws/ to the realtime service). */
function streamUrl(): string {
  const configured = import.meta.env.VITE_REALTIME_URL as string | undefined;
  if (configured) return configured;
  const scheme = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${scheme}//${window.location.host}/ws/v1/stream/`;
}

/** The tab's single connection. */
export const realtime = createRealtimeClient({
  fetchTicket: requestRealtimeTicket,
  url: streamUrl,
  createSocket: (url) => new WebSocket(url),
});

/** Runs the connection while signed in; logout (here or in another tab) or an account switch ends it. */
export function startRealtimeSync(
  store: { getState: () => Pick<RootState, 'auth'>; subscribe: (listener: () => void) => () => void },
  client: Pick<RealtimeClient, 'start' | 'stop'> = realtime,
): () => void {
  let session: string | null = null;
  const apply = () => {
    const { status, sessionUserId } = store.getState().auth;
    const wanted = status === 'authenticated' ? sessionUserId : null;
    if (wanted === session) return;
    session = wanted;
    client.stop();
    if (wanted) client.start();
  };
  apply();
  const unsubscribe = store.subscribe(apply);
  return () => {
    unsubscribe();
    client.stop();
  };
}

/** True while the socket is up; pollers slow down to a safety net. */
export function useRealtimeConnected(): boolean {
  return useSyncExternalStore(realtime.subscribeStatus, realtime.isConnected);
}

/** Bursts (a DM brings notification.created and message.created together) become one call. */
export const COALESCE_MS = 150;

/** Calls `onEvent` after matching events, at most once per COALESCE_MS window. */
export function useRealtime(match: (event: RealtimeEvent) => boolean, onEvent: () => void): void {
  const matchRef = useRef(match);
  const onEventRef = useRef(onEvent);

  useEffect(() => {
    matchRef.current = match;
    onEventRef.current = onEvent;
  }, [match, onEvent]);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    const unsubscribe = realtime.subscribe((event) => {
      if (timer !== undefined || !matchRef.current(event)) return;
      timer = setTimeout(() => {
        timer = undefined;
        onEventRef.current();
      }, COALESCE_MS);
    });
    return () => {
      unsubscribe();
      clearTimeout(timer);
    };
  }, []);
}

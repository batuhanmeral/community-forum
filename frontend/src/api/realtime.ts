import axios from 'axios';
import { api } from './client';

/** A one-time WebSocket ticket; null when the server runs without realtime (the app keeps polling). */
export async function requestRealtimeTicket(): Promise<string | null> {
  try {
    const { data } = await api.post<{ ticket: string }>('/realtime/ticket/');
    return data.ticket;
  } catch (err) {
    const status = axios.isAxiosError(err) ? err.response?.status : undefined;
    if (status === 503 || status === 404) return null;
    throw err;
  }
}

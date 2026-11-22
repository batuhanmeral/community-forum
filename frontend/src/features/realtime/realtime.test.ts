import { describe, expect, it, vi } from 'vitest';
import { configureStore } from '@reduxjs/toolkit';
import authReducer, { logout, sessionChanged, setAccessToken } from '@/features/auth/authSlice';
import { fakeJwt } from '@/test/fakeJwt';
import { startRealtimeSync } from './realtime';

function setup() {
  localStorage.clear();
  const store = configureStore({ reducer: { auth: authReducer } });
  const client = { start: vi.fn(), stop: vi.fn() };
  const stopSync = startRealtimeSync(store, client);
  return { store, client, stopSync };
}

describe('startRealtimeSync', () => {
  it('stays off while signed out', () => {
    const { client } = setup();
    expect(client.start).not.toHaveBeenCalled();
  });

  it('connects on sign-in and disconnects on logout', () => {
    const { store, client } = setup();
    store.dispatch(setAccessToken(fakeJwt({ user_id: '1' })));
    expect(client.start).toHaveBeenCalledTimes(1);
    // A refreshed token for the same user keeps the socket.
    store.dispatch(setAccessToken(fakeJwt({ user_id: '1' })));
    expect(client.start).toHaveBeenCalledTimes(1);
    client.stop.mockClear();
    store.dispatch(logout());
    expect(client.stop).toHaveBeenCalledTimes(1);
  });

  it('reconnects as the new user when another tab switches accounts', () => {
    const { store, client } = setup();
    store.dispatch(setAccessToken(fakeJwt({ user_id: '1' })));
    client.stop.mockClear();
    store.dispatch(sessionChanged('2'));
    expect(client.stop).toHaveBeenCalledTimes(1);
    expect(client.start).toHaveBeenCalledTimes(2);
  });

  it('disconnects when the sync is torn down', () => {
    const { store, client, stopSync } = setup();
    store.dispatch(setAccessToken(fakeJwt({ user_id: '1' })));
    client.stop.mockClear();
    stopSync();
    expect(client.stop).toHaveBeenCalledTimes(1);
  });
});

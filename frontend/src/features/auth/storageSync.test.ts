import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { store } from '@/app/store';
import { ACCESS_KEY, REFRESH_KEY, setTokens, setUser } from './authSlice';
import { startAuthStorageSync } from './storageSync';
import type { User } from './types';
import { fakeJwt as jwt } from '@/test/fakeJwt';

const alice: User = {
  id: 1,
  username: 'alice',
  email: 'a@x.com',
  email_verified: true,
  avatar: null,
  bio: '',
  show_nsfw: false,
  post_karma: 0,
  comment_karma: 0,
};

/** Simulates another tab writing the refresh token (storage events never fire in the writing tab). */
function otherTabWrites(access: string | null, refresh: string | null) {
  if (access === null) localStorage.removeItem(ACCESS_KEY);
  else localStorage.setItem(ACCESS_KEY, access);
  if (refresh === null) localStorage.removeItem(REFRESH_KEY);
  else localStorage.setItem(REFRESH_KEY, refresh);
  window.dispatchEvent(new StorageEvent('storage', { key: REFRESH_KEY, newValue: refresh }));
}

describe('startAuthStorageSync', () => {
  let stop: () => void;

  beforeEach(() => {
    localStorage.clear();
    store.dispatch(setTokens({ access: jwt({ user_id: 1 }), refresh: 'r1' }));
    store.dispatch(setUser(alice));
    stop = startAuthStorageSync(store);
  });

  afterEach(() => stop());

  it('logs this tab out when another tab removes the refresh token', () => {
    otherTabWrites(null, null);
    expect(store.getState().auth.refreshToken).toBeNull();
    expect(store.getState().auth.accessToken).toBeNull();
  });

  it('picks up tokens written by another tab', () => {
    // SimpleJWT may encode the id as a string; it still matches the numeric user id.
    const a4 = jwt({ user_id: '1' });
    otherTabWrites(a4, 'r4');
    expect(store.getState().auth.accessToken).toBe(a4);
    expect(store.getState().auth.refreshToken).toBe('r4');
    expect(store.getState().auth.user).toEqual(alice);
  });

  it('drops the cached user when another account signs in', () => {
    otherTabWrites(jwt({ user_id: 99 }), 'r5');
    expect(store.getState().auth.refreshToken).toBe('r5');
    expect(store.getState().auth.user).toBeNull();
  });

  it('logs this tab out when another tab clears localStorage', () => {
    localStorage.clear();
    window.dispatchEvent(new StorageEvent('storage', { key: null }));
    expect(store.getState().auth.refreshToken).toBeNull();
    expect(store.getState().auth.accessToken).toBeNull();
  });

  it('keeps the session on a clear event when the refresh token is still stored', () => {
    window.dispatchEvent(new StorageEvent('storage', { key: null }));
    expect(store.getState().auth.refreshToken).toBe('r1');
  });

  it('stops listening once unsubscribed', () => {
    stop();
    otherTabWrites(null, null);
    expect(store.getState().auth.refreshToken).toBe('r1');
  });
});

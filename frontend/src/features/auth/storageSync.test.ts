import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { store } from '@/app/store';
import { SESSION_KEY, setAccessToken, setUser } from './authSlice';
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

/** Simulates another tab writing the session marker (storage events never fire in the writing tab). */
function otherTabWrites(userId: string | null) {
  if (userId === null) localStorage.removeItem(SESSION_KEY);
  else localStorage.setItem(SESSION_KEY, userId);
  window.dispatchEvent(new StorageEvent('storage', { key: SESSION_KEY, newValue: userId }));
}

describe('startAuthStorageSync', () => {
  let stop: () => void;

  beforeEach(() => {
    localStorage.clear();
    store.dispatch(setAccessToken(jwt({ user_id: 1 })));
    store.dispatch(setUser(alice));
    stop = startAuthStorageSync(store);
  });

  afterEach(() => stop());

  it('logs this tab out when another tab logs out', () => {
    otherTabWrites(null);
    expect(store.getState().auth.sessionUserId).toBeNull();
    expect(store.getState().auth.accessToken).toBeNull();
  });

  it('keeps the session when the same account signs in again elsewhere', () => {
    otherTabWrites('1');
    expect(store.getState().auth.user).toEqual(alice);
    expect(store.getState().auth.accessToken).not.toBeNull();
  });

  it('drops the cached user and token when another account signs in', () => {
    otherTabWrites('99');
    expect(store.getState().auth.sessionUserId).toBe('99');
    expect(store.getState().auth.user).toBeNull();
    expect(store.getState().auth.accessToken).toBeNull();
  });

  it('logs this tab out when another tab clears localStorage', () => {
    localStorage.clear();
    window.dispatchEvent(new StorageEvent('storage', { key: null }));
    expect(store.getState().auth.sessionUserId).toBeNull();
  });

  it('keeps the session on a clear event when the marker is still stored', () => {
    window.dispatchEvent(new StorageEvent('storage', { key: null }));
    expect(store.getState().auth.sessionUserId).toBe('1');
  });

  it('stops listening once unsubscribed', () => {
    stop();
    otherTabWrites(null);
    expect(store.getState().auth.sessionUserId).toBe('1');
  });
});

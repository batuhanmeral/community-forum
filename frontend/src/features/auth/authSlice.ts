import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import type { User } from './types';
import { jwtUserId } from './jwt';

/** Non-secret marker (the user id) telling every tab a session exists; the refresh token is an HttpOnly cookie. */
export const SESSION_KEY = 'nexus.session';
// Tokens older builds kept in localStorage; dropped so a stale refresh token doesn't linger there.
const LEGACY_TOKEN_KEYS = ['nexus.access', 'nexus.refresh'];

export function readSessionUserId(): string | null {
  return localStorage.getItem(SESSION_KEY);
}

LEGACY_TOKEN_KEYS.forEach((key) => localStorage.removeItem(key));

interface AuthState {
  user: User | null;
  /** Kept in memory only; restored from the refresh cookie on load. */
  accessToken: string | null;
  sessionUserId: string | null;
  status: 'idle' | 'loading' | 'authenticated' | 'error';
  error: string | null;
}

const storedSession = readSessionUserId();

const initialState: AuthState = {
  user: null,
  accessToken: null,
  sessionUserId: storedSession,
  status: storedSession ? 'authenticated' : 'idle',
  error: null,
};

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    authStart(state) {
      state.status = 'loading';
      state.error = null;
    },
    authFailure(state, action: PayloadAction<string>) {
      state.status = 'error';
      state.error = action.payload;
    },
    setAccessToken(state, action: PayloadAction<string>) {
      const userId = jwtUserId(action.payload);
      if (state.user && String(state.user.id) !== userId) state.user = null;
      state.accessToken = action.payload;
      state.sessionUserId = userId;
      state.status = 'authenticated';
      if (userId) localStorage.setItem(SESSION_KEY, userId);
    },
    // Another tab signed in as someone else: drop this tab's account; the next request restores the new one.
    sessionChanged(state, action: PayloadAction<string>) {
      state.user = null;
      state.accessToken = null;
      state.sessionUserId = action.payload;
      state.status = 'authenticated';
    },
    setUser(state, action: PayloadAction<User>) {
      state.user = action.payload;
      state.status = 'authenticated';
      state.error = null;
    },
    logout(state) {
      state.user = null;
      state.accessToken = null;
      state.sessionUserId = null;
      state.status = 'idle';
      state.error = null;
      localStorage.removeItem(SESSION_KEY);
    },
  },
});

export const { authStart, authFailure, setAccessToken, sessionChanged, setUser, logout } =
  authSlice.actions;
export default authSlice.reducer;

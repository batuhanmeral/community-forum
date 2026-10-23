import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import type { AuthTokens, User } from './types';
import { jwtUserId } from './jwt';

export const ACCESS_KEY = 'nexus.access';
export const REFRESH_KEY = 'nexus.refresh';

export function readStoredTokens(): { access: string | null; refresh: string | null } {
  return { access: localStorage.getItem(ACCESS_KEY), refresh: localStorage.getItem(REFRESH_KEY) };
}

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  status: 'idle' | 'loading' | 'authenticated' | 'error';
  error: string | null;
}

const initialState: AuthState = {
  user: null,
  accessToken: localStorage.getItem(ACCESS_KEY),
  refreshToken: localStorage.getItem(REFRESH_KEY),
  status: localStorage.getItem(ACCESS_KEY) ? 'authenticated' : 'idle',
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
    setTokens(state, action: PayloadAction<AuthTokens>) {
      state.accessToken = action.payload.access;
      state.refreshToken = action.payload.refresh;
      localStorage.setItem(ACCESS_KEY, action.payload.access);
      localStorage.setItem(REFRESH_KEY, action.payload.refresh);
    },
    setAccessToken(state, action: PayloadAction<string>) {
      state.accessToken = action.payload;
      localStorage.setItem(ACCESS_KEY, action.payload);
    },
    // State only: the tokens are already in localStorage, written by another tab.
    syncFromStorage(state, action: PayloadAction<AuthTokens>) {
      if (state.user && jwtUserId(action.payload.access) !== String(state.user.id)) {
        state.user = null;
      }
      state.accessToken = action.payload.access;
      state.refreshToken = action.payload.refresh;
    },
    setUser(state, action: PayloadAction<User>) {
      state.user = action.payload;
      state.status = 'authenticated';
      state.error = null;
    },
    logout(state) {
      state.user = null;
      state.accessToken = null;
      state.refreshToken = null;
      state.status = 'idle';
      state.error = null;
      localStorage.removeItem(ACCESS_KEY);
      localStorage.removeItem(REFRESH_KEY);
    },
  },
});

export const {
  authStart,
  authFailure,
  setTokens,
  setAccessToken,
  syncFromStorage,
  setUser,
  logout,
} = authSlice.actions;
export default authSlice.reducer;

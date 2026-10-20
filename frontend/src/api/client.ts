import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios';
import { store } from '@/app/store';
import {
  logout,
  readStoredTokens,
  setAccessToken,
  setTokens,
  syncFromStorage,
} from '@/features/auth/authSlice';

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1';

export const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  const token = store.getState().auth.accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let refreshPromise: Promise<string | null> | null = null;

/** 400/401 mean the refresh token itself is dead; 429, 5xx and network errors are transient. */
function isTokenRejection(err: unknown): boolean {
  const status = axios.isAxiosError(err) ? err.response?.status : undefined;
  return status === 400 || status === 401;
}

/** Serialises refresh and logout across tabs (Web Locks); unlocked without it (jsdom, old browsers).
 * The lock is not re-entrant, so `fn` must not trigger a refresh (auth endpoints never do). */
export function withAuthLock<T>(fn: () => Promise<T>): Promise<T> {
  return navigator.locks?.request('nexus.auth.refresh', fn) ?? fn();
}

/** Takes over the tokens in localStorage; when they are gone, a logout already happened elsewhere. */
function adoptStoredTokens(): string | null {
  const { access, refresh } = readStoredTokens();
  if (!access || !refresh) {
    store.dispatch(logout());
    return null;
  }
  store.dispatch(syncFromStorage({ access, refresh }));
  return access;
}

async function refreshUnderLock(failedAccess: string | null): Promise<string | null> {
  // localStorage is shared by all tabs, so it holds the newest tokens, not this tab's store.
  const { access, refresh } = readStoredTokens();
  // No refresh token means a logout elsewhere; a different access token means another tab refreshed.
  if (!refresh || (access && access !== failedAccess)) return adoptStoredTokens();
  try {
    const res = await axios.post(`${BASE_URL}/auth/refresh/`, { refresh });
    // A logout or another tab's refresh during the request wins; storing this pair would undo it.
    if (readStoredTokens().refresh !== refresh) return adoptStoredTokens();
    const newAccess = res.data.access as string;
    // ROTATE_REFRESH_TOKENS blacklists the old refresh token, so the rotated
    // one returned here must replace it or the next refresh fails.
    const newRefresh = res.data.refresh as string | undefined;
    if (newRefresh) {
      store.dispatch(setTokens({ access: newAccess, refresh: newRefresh }));
    } else {
      store.dispatch(setAccessToken(newAccess));
    }
    return newAccess;
  } catch (err) {
    if (!isTokenRejection(err)) return null;
    // A rejected token that another tab already rotated away is not a reason to log out.
    if (readStoredTokens().refresh !== refresh) return adoptStoredTokens();
    store.dispatch(logout());
    return null;
  }
}

function refreshAccessToken(failedAccess: string | null): Promise<string | null> {
  return withAuthLock(() => refreshUnderLock(failedAccess));
}

interface RetryConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const original = error.config as RetryConfig | undefined;
    if (!original || error.response?.status !== 401 || original._retry) {
      return Promise.reject(error);
    }
    // Skip refresh for auth endpoints themselves
    if (original.url?.includes('/auth/')) {
      return Promise.reject(error);
    }
    original._retry = true;
    const sentAuth = original.headers.Authorization;
    const failedAccess = typeof sentAuth === 'string' ? sentAuth.replace(/^Bearer /, '') : null;
    if (!refreshPromise) {
      refreshPromise = refreshAccessToken(failedAccess).finally(() => {
        refreshPromise = null;
      });
    }
    const newToken = await refreshPromise;
    if (!newToken) {
      return Promise.reject(error);
    }
    original.headers.Authorization = `Bearer ${newToken}`;
    return api(original);
  },
);

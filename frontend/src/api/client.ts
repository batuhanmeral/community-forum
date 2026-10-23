import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios';
import { store } from '@/app/store';
import { logout, readSessionUserId, setAccessToken } from '@/features/auth/authSlice';

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1';

/** Refresh and logout run under the cross-tab lock; a hung request must not hold it forever. */
export const AUTH_REQUEST_TIMEOUT_MS = 10_000;

export const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  // The refresh token is an HttpOnly cookie (scoped to /auth/); the dev server is another origin.
  withCredentials: true,
});

let refreshPromise: Promise<string | null> | null = null;

api.interceptors.request.use(async (config) => {
  let token = store.getState().auth.accessToken;
  // After a reload only the cookie survives: restore the access token before the first request.
  if (!token && store.getState().auth.sessionUserId && !config.url?.includes('/auth/')) {
    token = await sharedRefresh(null);
  }
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

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

async function refreshUnderLock(failedAccess: string | null): Promise<string | null> {
  // Another request in this tab refreshed while this one waited for the lock.
  const current = store.getState().auth.accessToken;
  if (current && current !== failedAccess) return current;
  // The cookie is shared by all tabs; a missing session marker means a logout happened elsewhere.
  const session = readSessionUserId();
  if (!session) {
    store.dispatch(logout());
    return null;
  }
  try {
    const res = await axios.post(`${BASE_URL}/auth/refresh/`, null, {
      timeout: AUTH_REQUEST_TIMEOUT_MS,
      withCredentials: true,
    });
    // A logout or sign-in elsewhere during the request wins; adopting this token would undo it.
    const after = readSessionUserId();
    if (after !== session) {
      if (!after) store.dispatch(logout());
      return null;
    }
    const access = res.data.access as string;
    store.dispatch(setAccessToken(access));
    return access;
  } catch (err) {
    if (!isTokenRejection(err)) return null;
    store.dispatch(logout());
    return null;
  }
}

function sharedRefresh(failedAccess: string | null): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = withAuthLock(() => refreshUnderLock(failedAccess)).finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
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
    const newToken = await sharedRefresh(failedAccess);
    if (!newToken) {
      return Promise.reject(error);
    }
    original.headers.Authorization = `Bearer ${newToken}`;
    return api(original);
  },
);

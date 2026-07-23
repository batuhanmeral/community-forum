import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios';
import { store } from '@/app/store';
import { logout, setAccessToken, setTokens } from '@/features/auth/authSlice';

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

async function refreshAccessToken(): Promise<string | null> {
  const refresh = store.getState().auth.refreshToken;
  if (!refresh) return null;
  try {
    const res = await axios.post(`${BASE_URL}/auth/refresh/`, { refresh });
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
  } catch {
    store.dispatch(logout());
    return null;
  }
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
    if (!refreshPromise) {
      refreshPromise = refreshAccessToken().finally(() => {
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

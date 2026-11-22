import { AUTH_REQUEST_TIMEOUT_MS, api, withAuthLock } from './client';
import { readSessionUserId } from '@/features/auth/authSlice';
import type { AuthTokens, MfaChallenge, User } from '@/features/auth/types';

export interface RegisterPayload {
  username: string;
  email: string;
  password: string;
}

export interface LoginPayload {
  username: string;
  password: string;
}

export async function register(payload: RegisterPayload): Promise<User> {
  const res = await api.post<User>('/auth/register/', payload);
  return res.data;
}

// Set when a logout request failed: the HttpOnly cookie may still hold a live session.
const LOGOUT_PENDING_KEY = 'nexus.logoutPending';

export type LoginResult = AuthTokens | MfaChallenge;

export function needsSecondFactor(result: LoginResult): result is MfaChallenge {
  return 'mfa_required' in result;
}

export async function login(payload: LoginPayload): Promise<LoginResult> {
  // Callers hold the cross-tab auth lock; a hung login must not block every tab's refresh.
  const res = await api.post<LoginResult>('/auth/login/', payload, { timeout: AUTH_REQUEST_TIMEOUT_MS });
  // A challenge sets no cookie; only a real session replaced the old one.
  if (!needsSecondFactor(res.data)) localStorage.removeItem(LOGOUT_PENDING_KEY);
  return res.data;
}

/** Second login step: the one-time token from `login` plus an authenticator or recovery code. */
export async function verifyMfa(mfaToken: string, code: string): Promise<AuthTokens> {
  const res = await api.post<AuthTokens>(
    '/auth/mfa/verify/',
    { mfa_token: mfaToken, code },
    { timeout: AUTH_REQUEST_TIMEOUT_MS },
  );
  localStorage.removeItem(LOGOUT_PENDING_KEY);
  return res.data;
}

export async function fetchMe(): Promise<User> {
  const res = await api.get<User>('/users/me/');
  return res.data;
}

/** Blacklists the refresh cookie and asks the server to clear it; a failure is retried on the next load. */
export async function logoutRequest(): Promise<void> {
  try {
    await api.post('/auth/logout/', null, { timeout: AUTH_REQUEST_TIMEOUT_MS });
    localStorage.removeItem(LOGOUT_PENDING_KEY);
  } catch {
    localStorage.setItem(LOGOUT_PENDING_KEY, '1');
  }
}

/** Finishes a logout whose request failed, unless someone has signed in since. */
export async function retryPendingLogout(): Promise<void> {
  if (!localStorage.getItem(LOGOUT_PENDING_KEY)) return;
  // Re-checked under the lock: a login in another tab clears the flag under the same lock.
  await withAuthLock(async () => {
    if (localStorage.getItem(LOGOUT_PENDING_KEY) && !readSessionUserId()) await logoutRequest();
  });
}

export async function requestPasswordReset(email: string): Promise<void> {
  await api.post('/auth/password-reset/', { email });
}

export async function confirmPasswordReset(
  uid: string,
  token: string,
  newPassword: string,
): Promise<void> {
  await api.post('/auth/password-reset/confirm/', { uid, token, new_password: newPassword });
}

export async function verifyEmail(uid: string, token: string): Promise<void> {
  await api.post('/auth/verify-email/', { uid, token });
}

export async function resendVerificationEmail(): Promise<void> {
  await api.post('/auth/verify-email/resend/');
}

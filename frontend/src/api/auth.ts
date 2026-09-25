import { api } from './client';
import type { AuthTokens, User } from '@/features/auth/types';

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

export async function login(payload: LoginPayload): Promise<AuthTokens> {
  const res = await api.post<AuthTokens>('/auth/login/', payload);
  return res.data;
}

export async function fetchMe(): Promise<User> {
  const res = await api.get<User>('/users/me/');
  return res.data;
}

export async function logoutRequest(refresh: string): Promise<void> {
  await api.post('/auth/logout/', { refresh }).catch(() => undefined);
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

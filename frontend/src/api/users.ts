import { AUTH_REQUEST_TIMEOUT_MS, api } from './client';
import type { Paginated } from '@/features/communities/types';
import type { Post } from '@/features/posts/types';
import type { Comment } from '@/features/comments/types';
import type { AuthTokens, User } from '@/features/auth/types';

export interface UserProfile {
  id: number;
  username: string;
  email?: string;
  avatar: string | null;
  bio: string;
  country: string;
  post_karma: number;
  comment_karma: number;
  total_karma: number;
  followers_count: number;
  following_count: number;
  is_following: boolean;
  is_blocked: boolean;
  date_joined: string;
}

export async function getLeaderboard(): Promise<UserProfile[]> {
  const res = await api.get<UserProfile[]>('/users/leaderboard/');
  return res.data;
}

export async function getUserProfile(username: string): Promise<UserProfile> {
  const res = await api.get<UserProfile>(`/users/${encodeURIComponent(username)}/`);
  return res.data;
}

export async function getUserPosts(username: string, page = 1): Promise<Paginated<Post>> {
  const res = await api.get<Paginated<Post>>(`/users/${encodeURIComponent(username)}/posts/`, {
    params: { page },
  });
  return res.data;
}

export async function getUserComments(username: string, page = 1): Promise<Paginated<Comment>> {
  const res = await api.get<Paginated<Comment>>(`/users/${encodeURIComponent(username)}/comments/`, {
    params: { page },
  });
  return res.data;
}

export interface UpdateProfilePayload {
  bio?: string;
  country?: string;
  avatar?: File | null;
}

export async function updateProfile(payload: UpdateProfilePayload): Promise<User> {
  if (payload.avatar) {
    const form = new FormData();
    if (payload.bio !== undefined) form.append('bio', payload.bio);
    if (payload.country !== undefined) form.append('country', payload.country);
    form.append('avatar', payload.avatar);
    const res = await api.patch<User>('/users/me/', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  }
  const res = await api.patch<User>('/users/me/', {
    bio: payload.bio ?? '',
    ...(payload.country !== undefined && { country: payload.country }),
  });
  return res.data;
}

export async function updatePreferences(payload: { show_nsfw: boolean }): Promise<User> {
  const res = await api.patch<User>('/users/me/', payload);
  return res.data;
}

export async function changePassword(
  currentPassword: string,
  newPassword: string,
): Promise<AuthTokens> {
  const res = await api.post<AuthTokens>('/users/me/password/', {
    current_password: currentPassword,
    new_password: newPassword,
  });
  return res.data;
}

/** Erases the account's personal data; the server checks the password and clears the session cookie. */
export async function deleteAccount(password: string): Promise<void> {
  await api.delete('/users/me/', { data: { password }, timeout: AUTH_REQUEST_TIMEOUT_MS });
}

/** The account's own data as a JSON file (KVKK/GDPR right of access). */
export async function downloadAccountExport(): Promise<Blob> {
  const res = await api.get<Blob>('/users/me/export/', { responseType: 'blob' });
  return res.data;
}

export interface UnreadCounts {
  notifications: number;
  messages: number;
}

export async function getUnreadCounts(): Promise<UnreadCounts> {
  const res = await api.get<UnreadCounts>('/users/me/unread-counts/');
  return res.data;
}

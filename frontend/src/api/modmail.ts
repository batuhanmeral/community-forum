import { api } from './client';
import type { Paginated } from '@/features/communities/types';

export type ModmailStatus = 'open' | 'archived';

export interface ModmailThread {
  id: number;
  community: string;
  subject: string;
  status: ModmailStatus;
  creator_username: string | null;
  unread: boolean;
  created: string;
  updated: string;
  /** Only present for moderators. */
  assigned_to?: number | null;
  assigned_to_username?: string | null;
}

export interface ModmailMessage {
  id: number;
  author_username: string | null;
  from_moderator: boolean;
  body: string;
  /** Only present for moderators. */
  is_internal?: boolean;
  created: string;
}

export async function createModmailThread(
  slug: string,
  subject: string,
  body: string,
): Promise<ModmailThread> {
  const res = await api.post<ModmailThread>(`/communities/${slug}/modmail/`, { subject, body });
  return res.data;
}

export async function listModmailInbox(
  slug: string,
  status: ModmailStatus,
  page = 1,
): Promise<Paginated<ModmailThread>> {
  const res = await api.get<Paginated<ModmailThread>>(`/communities/${slug}/modmail/`, {
    params: { status, page },
  });
  return res.data;
}

export async function listMyModmail(page = 1): Promise<Paginated<ModmailThread>> {
  const res = await api.get<Paginated<ModmailThread>>('/modmail/mine/', { params: { page } });
  return res.data;
}

export async function getModmailThread(id: number): Promise<ModmailThread> {
  const res = await api.get<ModmailThread>(`/modmail/${id}/`);
  return res.data;
}

export async function updateModmailThread(
  id: number,
  patch: { status?: ModmailStatus; assigned_to?: number | null },
): Promise<ModmailThread> {
  const res = await api.patch<ModmailThread>(`/modmail/${id}/`, patch);
  return res.data;
}

export async function listModmailMessages(
  id: number,
  page = 1,
): Promise<Paginated<ModmailMessage>> {
  const res = await api.get<Paginated<ModmailMessage>>(`/modmail/${id}/messages/`, {
    params: { page },
  });
  return res.data;
}

export async function sendModmailMessage(
  id: number,
  body: string,
  isInternal = false,
): Promise<ModmailMessage> {
  const res = await api.post<ModmailMessage>(`/modmail/${id}/messages/`, {
    body,
    is_internal: isInternal,
  });
  return res.data;
}

export async function markModmailRead(id: number): Promise<void> {
  await api.post(`/modmail/${id}/read/`);
}

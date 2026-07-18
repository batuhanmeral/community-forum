import { api } from './client';
import type { Paginated } from '@/features/communities/types';
import type { Notification } from '@/features/notifications/types';

export async function listNotifications(params: { unread?: boolean; page?: number } = {}): Promise<Paginated<Notification>> {
  const query: Record<string, unknown> = {};
  if (params.unread) query.unread = 'true';
  if (params.page) query.page = params.page;
  const res = await api.get<Paginated<Notification>>('/notifications/', { params: query });
  return res.data;
}

export async function markNotificationRead(id: number): Promise<Notification> {
  const res = await api.post<Notification>(`/notifications/${id}/read/`);
  return res.data;
}

export async function markAllNotificationsRead(): Promise<{ marked_read: number }> {
  const res = await api.post<{ marked_read: number }>('/notifications/mark_all_read/');
  return res.data;
}

import { api } from './client';
import type { CommunityRole, Paginated } from '@/features/communities/types';

export type ReportTarget = 'post' | 'comment' | 'user';
export type ReportStatus = 'open' | 'resolved' | 'dismissed';

export interface Report {
  id: number;
  reporter: number;
  reporter_username: string;
  target_type: string;
  object_id: number;
  reason: string;
  status: ReportStatus;
  created_at: string;
}

export async function reportContent(
  target: ReportTarget,
  objectId: number,
  reason: string,
): Promise<Report> {
  const res = await api.post<Report>('/reports/', {
    content_type: target,
    object_id: objectId,
    reason,
  });
  return res.data;
}

export async function listModReports(
  slug: string,
  status?: ReportStatus,
): Promise<Report[]> {
  const res = await api.get<Report[] | Paginated<Report>>(
    `/communities/${slug}/mod/reports/`,
    { params: status ? { status } : undefined },
  );
  return Array.isArray(res.data) ? res.data : res.data.results;
}

export async function resolveReport(slug: string, id: number): Promise<Report> {
  const res = await api.post<Report>(`/communities/${slug}/mod/reports/${id}/resolve/`);
  return res.data;
}

export async function dismissReport(slug: string, id: number): Promise<Report> {
  const res = await api.post<Report>(`/communities/${slug}/mod/reports/${id}/dismiss/`);
  return res.data;
}

export interface MembershipRole {
  id: number;
  user: number;
  community: number;
  role: CommunityRole;
  is_banned: boolean;
  joined_at: string;
}

export async function banUser(slug: string, username: string): Promise<MembershipRole> {
  const res = await api.post<MembershipRole>(`/communities/${slug}/mod/ban/${username}/`);
  return res.data;
}

export async function unbanUser(slug: string, username: string): Promise<void> {
  await api.delete(`/communities/${slug}/mod/ban/${username}/`);
}

export type ModLogAction =
  | 'post_pin'
  | 'post_unpin'
  | 'post_approve'
  | 'post_reject'
  | 'post_remove'
  | 'comment_remove'
  | 'user_ban'
  | 'user_unban'
  | 'role_change'
  | 'report_resolve'
  | 'report_dismiss'
  | 'automod_hold';

export interface ModLogEntry {
  id: number;
  actor: number | null;
  actor_username: string | null;
  action: ModLogAction;
  target_type: string | null;
  object_id: number | null;
  detail: string;
  created_at: string;
}

export async function listModLog(slug: string, page = 1): Promise<Paginated<ModLogEntry>> {
  const res = await api.get<Paginated<ModLogEntry>>(`/communities/${slug}/mod/log/`, {
    params: { page },
  });
  return res.data;
}

export async function setMemberRole(
  slug: string,
  username: string,
  role: CommunityRole,
): Promise<MembershipRole> {
  const res = await api.patch<MembershipRole>(
    `/communities/${slug}/mod/members/${username}/`,
    { role },
  );
  return res.data;
}

export interface BannedMember {
  id: number;
  username: string;
  avatar: string | null;
  banned_by_username: string | null;
  banned_at: string | null;
  joined_at: string;
}

export async function listBans(slug: string, page = 1): Promise<Paginated<BannedMember>> {
  const res = await api.get<Paginated<BannedMember>>(`/communities/${slug}/mod/bans/`, {
    params: { page },
  });
  return res.data;
}

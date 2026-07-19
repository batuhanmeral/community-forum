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

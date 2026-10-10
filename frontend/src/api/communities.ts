import { api } from './client';
import type {
  Community,
  CommunityRule,
  Flair,
  Membership,
  NotifyLevel,
  Paginated,
} from '@/features/communities/types';

export interface ListParams {
  search?: string;
  page?: number;
  page_size?: number;
  ordering?: string;
  joined?: boolean;
}

export async function listCommunities(params: ListParams = {}): Promise<Paginated<Community>> {
  const res = await api.get<Paginated<Community>>('/communities/', { params });
  return res.data;
}

export async function getCommunity(slug: string): Promise<Community> {
  const res = await api.get<Community>(`/communities/${slug}/`);
  return res.data;
}

export interface CreateCommunityPayload {
  slug: string;
  name: string;
  description?: string;
  is_nsfw?: boolean;
  avatar?: File | null;
}

export async function createCommunity(payload: CreateCommunityPayload): Promise<Community> {
  if (payload.avatar) {
    const form = new FormData();
    form.append('slug', payload.slug);
    form.append('name', payload.name);
    if (payload.description) form.append('description', payload.description);
    if (payload.is_nsfw) form.append('is_nsfw', 'true');
    form.append('avatar', payload.avatar);
    const res = await api.post<Community>('/communities/', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  }
  const res = await api.post<Community>('/communities/', {
    slug: payload.slug,
    name: payload.name,
    description: payload.description ?? '',
    is_nsfw: payload.is_nsfw ?? false,
  });
  return res.data;
}

export interface UpdateCommunityPayload {
  name?: string;
  description?: string;
  is_nsfw?: boolean;
  requires_approval?: boolean;
  avatar?: File | null;
  banned_keywords?: string;
}

export async function updateCommunity(
  slug: string,
  payload: UpdateCommunityPayload,
): Promise<Community> {
  if (payload.avatar) {
    const form = new FormData();
    if (payload.name !== undefined) form.append('name', payload.name);
    if (payload.description !== undefined) form.append('description', payload.description);
    if (payload.is_nsfw !== undefined) form.append('is_nsfw', String(payload.is_nsfw));
    if (payload.requires_approval !== undefined)
      form.append('requires_approval', String(payload.requires_approval));
    if (payload.banned_keywords !== undefined)
      form.append('banned_keywords', payload.banned_keywords);
    form.append('avatar', payload.avatar);
    const res = await api.patch<Community>(`/communities/${slug}/`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  }
  const rest = { ...payload };
  delete rest.avatar;
  const res = await api.patch<Community>(`/communities/${slug}/`, rest);
  return res.data;
}

export async function joinCommunity(slug: string): Promise<Membership> {
  const res = await api.post<Membership>(`/communities/${slug}/membership/`);
  return res.data;
}

export async function leaveCommunity(slug: string): Promise<void> {
  await api.delete(`/communities/${slug}/membership/`);
}

export async function updateNotifyLevel(
  slug: string,
  notify_level: NotifyLevel,
): Promise<Membership> {
  const res = await api.patch<Membership>(`/communities/${slug}/membership/`, {
    notify_level,
  });
  return res.data;
}

export async function listRules(slug: string): Promise<CommunityRule[]> {
  const res = await api.get<CommunityRule[] | Paginated<CommunityRule>>(
    `/communities/${slug}/rules/`,
  );
  return Array.isArray(res.data) ? res.data : res.data.results;
}

export async function listFlairs(slug: string): Promise<Flair[]> {
  const res = await api.get<Flair[]>(`/communities/${slug}/flairs/`);
  return res.data;
}

export async function createFlair(slug: string, name: string, color: string): Promise<Flair> {
  const res = await api.post<Flair>(`/communities/${slug}/flairs/`, { name, color });
  return res.data;
}

export async function deleteFlair(slug: string, id: number): Promise<void> {
  await api.delete(`/communities/${slug}/flairs/${id}/`);
}

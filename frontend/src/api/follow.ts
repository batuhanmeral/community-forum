import { api } from './client';
import type { Paginated } from '@/features/communities/types';

export interface FollowUser {
  id: number;
  username: string;
  avatar: string | null;
  is_following: boolean;
}

export async function followUser(username: string): Promise<void> {
  await api.post(`/users/${username}/follow/`);
}

export async function unfollowUser(username: string): Promise<void> {
  await api.delete(`/users/${username}/follow/`);
}

export async function listFollowers(username: string, page = 1): Promise<Paginated<FollowUser>> {
  const res = await api.get<Paginated<FollowUser>>(`/users/${username}/followers/`, { params: { page } });
  return res.data;
}

export async function listFollowing(username: string, page = 1): Promise<Paginated<FollowUser>> {
  const res = await api.get<Paginated<FollowUser>>(`/users/${username}/following/`, { params: { page } });
  return res.data;
}

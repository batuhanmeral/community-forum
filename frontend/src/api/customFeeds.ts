import { api } from './client';
import type { Paginated } from '@/features/communities/types';
import type { Post } from '@/features/posts/types';
import type { SortOption, TimeWindow } from './posts';

export interface CustomFeed {
  id: number;
  name: string;
  slug: string;
  description: string;
  is_public: boolean;
  owner_username: string;
  communities: string[];
  created: string;
}

export interface CustomFeedInput {
  name: string;
  description: string;
  is_public: boolean;
  communities: string[];
}

export async function listMyFeeds(): Promise<Paginated<CustomFeed>> {
  const res = await api.get<Paginated<CustomFeed>>('/users/me/feeds/');
  return res.data;
}

export async function createFeed(input: CustomFeedInput): Promise<CustomFeed> {
  const res = await api.post<CustomFeed>('/users/me/feeds/', input);
  return res.data;
}

export async function getFeed(username: string, slug: string): Promise<CustomFeed> {
  const res = await api.get<CustomFeed>(`/users/${encodeURIComponent(username)}/feeds/${slug}/`);
  return res.data;
}

export async function updateFeed(
  username: string,
  slug: string,
  input: Partial<CustomFeedInput>,
): Promise<CustomFeed> {
  const res = await api.patch<CustomFeed>(`/users/${encodeURIComponent(username)}/feeds/${slug}/`, input);
  return res.data;
}

export async function deleteFeed(username: string, slug: string): Promise<void> {
  await api.delete(`/users/${encodeURIComponent(username)}/feeds/${slug}/`);
}

export async function listFeedPosts(
  username: string,
  slug: string,
  params: { sort?: SortOption; t?: TimeWindow; page?: number } = {},
): Promise<Paginated<Post>> {
  const res = await api.get<Paginated<Post>>(
    `/users/${encodeURIComponent(username)}/feeds/${slug}/posts/`,
    { params },
  );
  return res.data;
}

import { api } from './client';
import type { Community, Paginated } from '@/features/communities/types';
import type { Post } from '@/features/posts/types';

export async function trendingCommunities(): Promise<Community[]> {
  const res = await api.get<Community[] | Paginated<Community>>('/trending/communities/');
  return Array.isArray(res.data) ? res.data : res.data.results;
}

export async function trendingPosts(): Promise<Post[]> {
  const res = await api.get<Post[] | Paginated<Post>>('/trending/posts/');
  return Array.isArray(res.data) ? res.data : res.data.results;
}

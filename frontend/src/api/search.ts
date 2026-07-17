import { api } from './client';
import type { Paginated } from '@/features/communities/types';

export interface UserSearchResult {
  id: number;
  username: string;
  avatar: string | null;
}

export async function searchUsers(q: string, page = 1): Promise<Paginated<UserSearchResult>> {
  const res = await api.get<Paginated<UserSearchResult>>('/search/', {
    params: { q, type: 'user', page },
  });
  return res.data;
}

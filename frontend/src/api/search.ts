import { api } from './client';
import type { Community, Paginated } from '@/features/communities/types';
import type { Post } from '@/features/posts/types';
import type { UserProfile } from './users';

export type SearchType = 'post' | 'community' | 'user';

export interface SearchResultMap {
  post: Post;
  community: Community;
  user: UserProfile;
}

export async function search<T extends SearchType>(
  type: T,
  q: string,
  page = 1,
): Promise<Paginated<SearchResultMap[T]>> {
  const res = await api.get<Paginated<SearchResultMap[T]>>('/search/', {
    params: { q, type, page },
  });
  return res.data;
}

// Lightweight helper kept for the followers/mention pickers that only need users.
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

import { api } from './client';
import type { Paginated } from '@/features/communities/types';
import type { Post, PostKind } from '@/features/posts/types';

export type SortOption = 'new' | 'top' | 'hot';
export type TimeWindow = 'hour' | 'day' | 'week' | 'month' | 'year' | 'all';

export interface ListPostsParams {
  sort?: SortOption;
  t?: TimeWindow;
  nsfw?: 'show';
  page?: number;
  scope?: 'all';
}

export async function listCommunityPosts(
  slug: string,
  params: ListPostsParams = {},
): Promise<Paginated<Post>> {
  const res = await api.get<Paginated<Post>>(`/communities/${slug}/posts/`, { params });
  return res.data;
}

export async function listFeed(params: ListPostsParams = {}): Promise<Paginated<Post>> {
  const res = await api.get<Paginated<Post>>('/feed/', { params });
  return res.data;
}

export async function listFollowingFeed(params: ListPostsParams = {}): Promise<Paginated<Post>> {
  const res = await api.get<Paginated<Post>>('/feed/following/', { params });
  return res.data;
}

export async function getPost(id: number): Promise<Post> {
  const res = await api.get<Post>(`/posts/${id}/`);
  return res.data;
}

export interface CreatePostPayload {
  kind: PostKind;
  title: string;
  body?: string;
  url?: string;
  image?: File | null;
  is_nsfw?: boolean;
  flair?: number | null;
  poll_options?: string[];
  poll_closes_at?: string;
}

export async function createPost(slug: string, payload: CreatePostPayload): Promise<Post> {
  if (payload.kind === 'image' && payload.image) {
    const form = new FormData();
    form.append('kind', payload.kind);
    form.append('title', payload.title);
    if (payload.body) form.append('body', payload.body);
    if (payload.is_nsfw) form.append('is_nsfw', 'true');
    if (payload.flair) form.append('flair', String(payload.flair));
    form.append('image', payload.image);
    const res = await api.post<Post>(`/communities/${slug}/posts/`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  }
  const body: Record<string, unknown> = {
    kind: payload.kind,
    title: payload.title,
    body: payload.body ?? '',
    is_nsfw: payload.is_nsfw ?? false,
  };
  if (payload.flair) body.flair = payload.flair;
  if (payload.kind === 'link') body.url = payload.url ?? '';
  if (payload.kind === 'poll' && payload.poll_options && payload.poll_closes_at) {
    body.poll_input = {
      options: payload.poll_options.filter((o) => o.trim()),
      closes_at: payload.poll_closes_at,
    };
  }
  const res = await api.post<Post>(`/communities/${slug}/posts/`, body);
  return res.data;
}

export interface UpdatePostPayload {
  title?: string;
  body?: string;
  is_nsfw?: boolean;
}

export async function updatePost(id: number, payload: UpdatePostPayload): Promise<Post> {
  const res = await api.patch<Post>(`/posts/${id}/`, payload);
  return res.data;
}

export async function deletePost(id: number): Promise<void> {
  await api.delete(`/posts/${id}/`);
}

export async function setPostSticky(id: number, pinned: boolean): Promise<{ is_pinned: boolean }> {
  const res = pinned
    ? await api.post<{ is_pinned: boolean }>(`/posts/${id}/sticky/`)
    : await api.delete<{ is_pinned: boolean }>(`/posts/${id}/sticky/`);
  return res.data;
}

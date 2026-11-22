import { api } from './client';
import type { Paginated } from '@/features/communities/types';
import type { Post, PostKind, PostRevision } from '@/features/posts/types';

export type SortOption = 'new' | 'top' | 'hot';
export type TimeWindow = 'hour' | 'day' | 'week' | 'month' | 'year' | 'all';

export interface ListPostsParams {
  sort?: SortOption;
  t?: TimeWindow;
  nsfw?: 'show' | 'hide';
  page?: number;
  scope?: 'all';
  answered?: 'true' | 'false';
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
  is_spoiler?: boolean;
  is_question?: boolean;
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
    if (payload.is_spoiler) form.append('is_spoiler', 'true');
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
    is_spoiler: payload.is_spoiler ?? false,
  };
  if (payload.flair) body.flair = payload.flair;
  if (payload.is_question) body.is_question = true;
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
  is_spoiler?: boolean;
}

export async function updatePost(id: number, payload: UpdatePostPayload): Promise<Post> {
  const res = await api.patch<Post>(`/posts/${id}/`, payload);
  return res.data;
}

export async function setPostSpoiler(id: number, spoiler: boolean): Promise<{ is_spoiler: boolean }> {
  const res = spoiler
    ? await api.post<{ is_spoiler: boolean }>(`/posts/${id}/spoiler/`)
    : await api.delete<{ is_spoiler: boolean }>(`/posts/${id}/spoiler/`);
  return res.data;
}

export async function deletePost(id: number): Promise<void> {
}

export async function setPostSticky(id: number, pinned: boolean): Promise<{ is_pinned: boolean }> {
  const res = pinned
    ? await api.post<{ is_pinned: boolean }>(`/posts/${id}/sticky/`)
    : await api.delete<{ is_pinned: boolean }>(`/posts/${id}/sticky/`);
  return res.data;
}

export async function listApprovalQueue(slug: string, page = 1): Promise<Paginated<Post>> {
  const res = await api.get<Paginated<Post>>(`/communities/${slug}/mod/approval-queue/`, {
    params: { page },
  });
  return res.data;
}

// `editedAt` is the version the moderator saw; the server answers 409 if the post changed since.
export async function approvePost(id: number, editedAt: string | null): Promise<void> {
  await api.post(`/posts/${id}/approve/`, { edited_at: editedAt });
}

export async function rejectPost(id: number): Promise<void> {
  await api.delete(`/posts/${id}/approve/`);
}

export async function listPostRevisions(id: number, page = 1): Promise<Paginated<PostRevision>> {
  const res = await api.get<Paginated<PostRevision>>(`/posts/${id}/revisions/`, { params: { page } });
  return res.data;
}

export interface QaState {
  accepted_comment: number | null;
  bounty_amount: number;
  bounty_expires_at: string | null;
  bounty_status: Post['bounty_status'];
}

export async function acceptAnswer(postId: number, commentId: number): Promise<QaState> {
  const res = await api.post<QaState>(`/posts/${postId}/accept/`, { comment: commentId });
  return res.data;
}

export async function clearAcceptedAnswer(postId: number): Promise<QaState> {
  const res = await api.delete<QaState>(`/posts/${postId}/accept/`);
  return res.data;
}

export async function placeBounty(postId: number, amount: number): Promise<QaState> {
  const res = await api.post<QaState>(`/posts/${postId}/bounty/`, { amount });
  return res.data;
}

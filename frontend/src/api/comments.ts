import { api } from './client';
import type { Paginated } from '@/features/communities/types';
import type { Comment, CommentRevision, CommentSort } from '@/features/comments/types';

export async function listComments(
  postId: number,
  params: { sort?: CommentSort; page?: number } = {},
): Promise<Paginated<Comment>> {
  const res = await api.get<Paginated<Comment>>(`/posts/${postId}/comments/`, { params });
  return res.data;
}

export async function createComment(
  postId: number,
  body: string,
  parent: number | null = null,
): Promise<Comment> {
  const res = await api.post<Comment>(`/posts/${postId}/comments/`, { body, parent });
  return res.data;
}

export async function updateComment(id: number, body: string): Promise<Comment> {
  const res = await api.patch<Comment>(`/comments/${id}/`, { body });
  return res.data;
}

export async function deleteComment(id: number): Promise<void> {
  await api.delete(`/comments/${id}/`);
}

export async function listCommentRevisions(
  id: number,
  page = 1,
): Promise<Paginated<CommentRevision>> {
  const res = await api.get<Paginated<CommentRevision>>(`/comments/${id}/revisions/`, {
    params: { page },
  });
  return res.data;
}

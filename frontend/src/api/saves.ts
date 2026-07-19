import { api } from './client';
import type { Paginated } from '@/features/communities/types';
import type { Post } from '@/features/posts/types';
import type { Comment } from '@/features/comments/types';

export type SaveTarget = 'post' | 'comment';

export interface SavedItem {
  id: number;
  target_type: SaveTarget;
  object_id: number;
  target: Post | Comment | null;
  created_at: string;
}

export interface ToggleSaveResponse {
  is_saved: boolean;
}

export async function toggleSave(target: SaveTarget, objectId: number): Promise<ToggleSaveResponse> {
  const res = await api.post<ToggleSaveResponse>('/saved/', {
    content_type: target,
    object_id: objectId,
  });
  return res.data;
}

export async function listSaved(type?: SaveTarget, page = 1): Promise<Paginated<SavedItem>> {
  const params: Record<string, unknown> = { page };
  if (type) params.type = type;
  const res = await api.get<Paginated<SavedItem>>('/saved/', { params });
  return res.data;
}

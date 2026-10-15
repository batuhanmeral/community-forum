export interface Comment {
  id: number;
  post: number;
  author: number | null;
  author_username: string | null;
  parent: number | null;
  body: string;
  body_html: string;
  is_deleted: boolean;
  score: number;
  user_vote: number | null;
  is_saved: boolean;
  created_at: string;
  updated_at: string;
  edited_at: string | null;
}

export type CommentSort = 'best' | 'top' | 'new' | 'old' | 'controversial';

export interface CommentRevision {
  id: number;
  body: string;
  edited_at: string;
  edited_by: number | null;
  edited_by_username: string | null;
}

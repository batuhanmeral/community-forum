import type { Flair } from '@/features/communities/types';

export type PostKind = 'text' | 'link' | 'image' | 'poll';

export interface PollOption {
  id: number;
  text: string;
  order: number;
  vote_count: number;
  percent: number;
}

export interface Poll {
  id: number;
  closes_at: string;
  is_closed: boolean;
  total_votes: number;
  user_option: number | null;
  options: PollOption[];
}

export interface Post {
  id: number;
  author: number | null;
  author_username: string | null;
  community: string;
  flair: number | null;
  flair_detail: Flair | null;
  kind: PostKind;
  title: string;
  body: string;
  body_html: string;
  is_deleted: boolean;
  url: string;
  image: string | null;
  is_nsfw: boolean;
  is_pinned: boolean;
  score: number;
  comment_count: number;
  user_vote: number | null;
  is_saved: boolean;
  poll: Poll | null;
  created_at: string;
  edited_at: string | null;
}

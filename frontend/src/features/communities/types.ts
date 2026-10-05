export type NotifyLevel = 'all' | 'posts_only' | 'off';
export type CommunityRole = 'admin' | 'moderator' | 'member';

export interface Community {
  id: number;
  slug: string;
  name: string;
  description: string;
  avatar: string | null;
  is_nsfw: boolean;
  requires_approval: boolean;
  creator: number;
  created_at: string;
  member_count: number;
  is_member: boolean;
  is_banned: boolean;
  my_role: CommunityRole | null;
  /** AutoMod keywords, newline-separated. Only present for moderators/admins. */
  banned_keywords?: string;
}

export interface Membership {
  id: number;
  user: number;
  community: number;
  role: CommunityRole;
  notify_level: NotifyLevel;
  joined_at: string;
}

export interface CommunityRule {
  id: number;
  order: number;
  short: string;
  description: string;
  created_at: string;
}

export interface Flair {
  id: number;
  name: string;
  color: string;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

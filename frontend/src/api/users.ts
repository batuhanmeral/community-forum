import { api } from './client';

export interface UserProfile {
  id: number;
  username: string;
  email?: string;
  avatar: string | null;
  bio: string;
  post_karma: number;
  comment_karma: number;
  total_karma: number;
  followers_count: number;
  following_count: number;
  is_following: boolean;
  date_joined: string;
}

export async function getUserProfile(username: string): Promise<UserProfile> {
  const res = await api.get<UserProfile>(`/users/${username}/`);
  return res.data;
}

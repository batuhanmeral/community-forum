export interface User {
  id: number;
  username: string;
  email: string;
  avatar: string | null;
  bio: string;
  show_nsfw: boolean;
  post_karma: number;
  comment_karma: number;
}

export interface AuthTokens {
  access: string;
  refresh: string;
}

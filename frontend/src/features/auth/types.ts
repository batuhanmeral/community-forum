export interface User {
  id: number;
  username: string;
  email: string;
  email_verified: boolean;
  avatar: string | null;
  bio: string;
  show_nsfw: boolean;
  post_karma: number;
  comment_karma: number;
}

/** The refresh token never reaches page scripts: the server sets it as an HttpOnly cookie. */
export interface AuthTokens {
  access: string;
}

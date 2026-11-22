export interface User {
  id: number;
  username: string;
  email: string;
  email_verified: boolean;
  avatar: string | null;
  bio: string;
  country: string;
  show_nsfw: boolean;
  post_karma: number;
  comment_karma: number;
}

/** The refresh token never reaches page scripts: the server sets it as an HttpOnly cookie. */
export interface AuthTokens {
  access: string;
  /** Set when a recovery code (not an authenticator code) completed the login. */
  recovery_codes_remaining?: number;
}

/** Login answer when the account has two-factor authentication: no session yet. */
export interface MfaChallenge {
  mfa_required: true;
  mfa_token: string;
}

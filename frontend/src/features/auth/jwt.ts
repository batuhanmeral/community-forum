/** Reads SimpleJWT's `user_id` claim without verifying the token; null when it can't be parsed. */
export function jwtUserId(token: string): string | null {
  try {
    const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const userId = JSON.parse(atob(payload)).user_id;
    return userId == null ? null : String(userId);
  } catch {
    return null;
  }
}

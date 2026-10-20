// Usernames may hold reserved URL characters; always build profile links here.
export function userPath(username: string): string {
  return `/u/${encodeURIComponent(username)}`;
}

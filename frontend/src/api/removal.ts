/** Body of a moderator DELETE: the chosen removal reason and optional note. */
export function removalBody(removal: { reason: number | null; note: string }) {
  return {
    ...(removal.reason === null ? {} : { removal_reason: removal.reason }),
    ...(removal.note.trim() ? { removal_note: removal.note.trim() } : {}),
  };
}

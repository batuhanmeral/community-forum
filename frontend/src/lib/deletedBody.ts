const REMOVED_MARKER = '[removed]';

/** i18n key for a body the API masked on delete: "[removed]" by a moderator, "[deleted]" by the author. */
export function deletedBodyKey(body: string): 'common.removed' | 'common.deleted' {
  return body === REMOVED_MARKER ? 'common.removed' : 'common.deleted';
}

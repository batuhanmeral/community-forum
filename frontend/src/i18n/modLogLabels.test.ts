import { describe, expect, it } from 'vitest';
import { en } from './en';
import { tr } from './tr';

// Mirrors ModAction.Action on the server; every entry needs a label in both languages.
const ACTIONS = [
  'user_flair_create',
  'user_flair_update',
  'user_flair_delete',
  'user_flair_assign',
  'post_pin',
  'post_unpin',
  'post_spoiler',
  'post_unspoiler',
  'post_approve',
  'post_reject',
  'post_remove',
  'comment_remove',
  'user_ban',
  'user_unban',
  'role_change',
  'report_resolve',
  'report_dismiss',
  'automod_hold',
];

describe('mod log labels', () => {
  it.each([
    ['en', en],
    ['tr', tr],
  ])('%s has a label for every action', (_, dict) => {
    const mod = (dict as unknown as { mod: Record<string, string> }).mod;
    expect(ACTIONS.filter((a) => !mod[`log_${a}`])).toEqual([]);
  });
});

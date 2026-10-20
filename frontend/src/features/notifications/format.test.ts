import { describe, it, expect } from 'vitest';
import { formatNotification } from './format';
import type { Notification } from './types';

function make(overrides: Partial<Notification>): Notification {
  return {
    id: 1,
    recipient: 1,
    actor: 2,
    actor_username: 'alice',
    verb: 'comment',
    target_type: 'comment',
    target_id: 7,
    link: '/posts/42#comment-7',
    created_at: '2026-06-24T12:00:00Z',
    read_at: null,
    ...overrides,
  };
}

describe('formatNotification', () => {
  it('uses the server link for comment notifications', () => {
    const f = formatNotification(make({ verb: 'comment' }));
    expect(f.text).toBe('u/alice commented on your post');
    expect(f.to).toBe('/posts/42#comment-7');
  });

  it('links replies and mentions that live in comments', () => {
    expect(formatNotification(make({ verb: 'reply' })).to).toBe('/posts/42#comment-7');
    expect(formatNotification(make({ verb: 'mention' })).to).toBe('/posts/42#comment-7');
  });

  it('links a follow notification to the actor profile', () => {
    const f = formatNotification(
      make({ verb: 'follow', target_type: 'user', target_id: 2, link: '/u/alice' }),
    );
    expect(f.text).toContain('followed you');
    expect(f.to).toBe('/u/alice');
  });

  it('routes dm notifications to the conversation', () => {
    const f = formatNotification(make({ verb: 'dm', target_type: 'message', link: '/messages/3' }));
    expect(f.to).toBe('/messages/3');
  });

  it('falls back to "Someone" when the actor username is missing', () => {
    const f = formatNotification(make({ actor_username: null, verb: 'mention' }));
    expect(f.text).toMatch(/^Someone /);
  });

  it('is not clickable when the target is gone', () => {
    const f = formatNotification(
      make({ verb: 'mention', target_type: 'post', target_id: 42, link: null }),
    );
    expect(f.to).toBeNull();
  });

  it('has a default branch for unknown verbs', () => {
    const f = formatNotification(make({ verb: 'unknown' as Notification['verb'] }));
    expect(f.kind).toBe('other');
    expect(f.to).toBe('/posts/42#comment-7');
  });

  it('maps each verb to its kind and never returns an icon field', () => {
    const kinds = {
      comment: 'comment',
      reply: 'reply',
      mention: 'mention',
      follow: 'follow',
      dm: 'message',
      mod_action: 'mod',
    } as const;
    for (const [verb, kind] of Object.entries(kinds)) {
      const f = formatNotification(make({ verb: verb as Notification['verb'] }));
      expect(f.kind).toBe(kind);
      expect(f).not.toHaveProperty('icon');
    }
  });
});

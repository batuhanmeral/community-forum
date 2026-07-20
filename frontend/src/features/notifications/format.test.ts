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
    target_type: 'post',
    target_id: 42,
    created_at: '2026-06-24T12:00:00Z',
    read_at: null,
    ...overrides,
  };
}

describe('formatNotification', () => {
  it('links comment notifications to the target post', () => {
    const f = formatNotification(make({ verb: 'comment' }));
    expect(f.text).toBe('u/alice commented on your post');
    expect(f.to).toBe('/posts/42');
  });

  it('links a follow notification to the actor profile', () => {
    const f = formatNotification(make({ verb: 'follow' }));
    expect(f.text).toContain('followed you');
    expect(f.to).toBe('/u/alice');
  });

  it('routes dm notifications to the messages inbox', () => {
    const f = formatNotification(make({ verb: 'dm' }));
    expect(f.to).toBe('/messages');
  });

  it('falls back to "Someone" when the actor username is missing', () => {
    const f = formatNotification(make({ actor_username: null, verb: 'mention' }));
    expect(f.text).toMatch(/^Someone /);
  });

  it('does not produce a post link when target is not a post', () => {
    const f = formatNotification(make({ verb: 'comment', target_type: 'comment', target_id: 7 }));
    expect(f.to).toBeNull();
  });

  it('has a default branch for unknown verbs', () => {
    const f = formatNotification(make({ verb: 'unknown' as Notification['verb'] }));
    expect(f.icon).toBe('•');
    expect(f.to).toBeNull();
  });
});

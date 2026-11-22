import { describe, it, expect } from 'vitest';
import i18n from '@/i18n';
import { formatNotification as format } from './format';
import type { Notification } from './types';

const en = i18n.getFixedT('en');
const tr = i18n.getFixedT('tr');

function formatNotification(n: Notification, t = en) {
  return format(n, t);
}

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

  it.each([
    { label: 'reply', overrides: { verb: 'reply' }, expectedTo: '/posts/42#comment-7' },
    { label: 'mention', overrides: { verb: 'mention' }, expectedTo: '/posts/42#comment-7' },
    { label: 'DM', overrides: { verb: 'dm', target_type: 'message', link: '/messages/3' }, expectedTo: '/messages/3' },
    {
      label: 'mention with a gone target',
      overrides: { verb: 'mention', target_type: 'post', target_id: 42, link: null },
      expectedTo: null,
    },
  ] as const)('links a $label notification to $expectedTo', ({ overrides, expectedTo }) => {
    expect(formatNotification(make(overrides)).to).toBe(expectedTo);
  });

  it('links a follow notification to the actor profile', () => {
    const f = formatNotification(
      make({ verb: 'follow', target_type: 'user', target_id: 2, link: '/u/alice' }),
    );
    expect(f.text).toContain('followed you');
    expect(f.to).toBe('/u/alice');
  });

  it('falls back to "Someone" when the actor username is missing', () => {
    const f = formatNotification(make({ actor_username: null, verb: 'mention' }));
    expect(f.text).toMatch(/^Someone /);
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

  it('notification texts are translated', () => {
    const verbs = ['comment', 'reply', 'mention', 'follow', 'dm', 'mod_action', 'unknown'];
    for (const verb of verbs) {
      const f = formatNotification(make({ verb: verb as Notification['verb'] }), tr);
      expect(f.text).not.toMatch(/commented|replied|followed|mentioned|sent you|moderator|interacted/);
      expect(f.text).not.toBe('');
    }
  });

  it('names the actor and the target in the translated text', () => {
    expect(formatNotification(make({ verb: 'reply' }), tr).text).toContain('u/alice');
    expect(formatNotification(make({ verb: 'mod_action', target_type: 'post' })).text).toBe(
      'A moderator acted on your post',
    );
    expect(formatNotification(make({ verb: 'mod_action', target_type: null })).text).toBe(
      'A moderator acted on your content',
    );
  });

  it('shows the removal reason title and body', () => {
    const n = make({
      verb: 'removal',
      target_type: 'post',
      link: '/posts/9',
      reason_title: 'Spam',
      reason_body_html: '<p>No spam</p>',
    });
    const f = formatNotification(n);
    expect(f.text).toBe('A moderator removed your post: Spam');
    expect(f.detailHtml).toBe('<p>No spam</p>');
    expect(formatNotification(n, tr).text).toContain('Spam');
  });

  it('describes a modmail notification and links to the thread', () => {
    const f = formatNotification(
      make({ verb: 'modmail', target_type: 'modmailthread', link: '/modmail/3' }),
    );
    expect(f.text).toBe('New modmail message');
    expect(f.to).toBe('/modmail/3');
  });
});

describe('formatNotification Q&A verbs', () => {
  it.each([
    ['answer_accepted', 'answer', 'Your answer was accepted (+15 karma)'],
    ['bounty_awarded', 'bounty', 'You were awarded a bounty for your answer'],
    ['bounty_refunded', 'bounty', 'Your bounty was refunded'],
  ] as const)('formats %s in English and Turkish', (verb, kind, text) => {
    const n = make({ verb, actor: null, actor_username: null });
    expect(formatNotification(n)).toMatchObject({ kind, text, to: n.link });
    expect(formatNotification(n, tr).text).not.toBe(text);
  });
});

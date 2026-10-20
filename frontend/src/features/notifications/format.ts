import type { Notification } from './types';

export type NotificationKind = 'comment' | 'reply' | 'mention' | 'follow' | 'message' | 'mod' | 'other';

export interface FormattedNotification {
  kind: NotificationKind;
  text: string;
  to: string | null;
}

const ACTOR_FALLBACK = 'Someone';

export function formatNotification(n: Notification): FormattedNotification {
  const actor = n.actor_username ?? ACTOR_FALLBACK;
  const actorLabel = n.actor_username ? `u/${actor}` : actor;
  const to = n.link;

  switch (n.verb) {
    case 'comment':
      return { kind: 'comment', text: `${actorLabel} commented on your post`, to };
    case 'reply':
      return { kind: 'reply', text: `${actorLabel} replied to your comment`, to };
    case 'mention':
      return { kind: 'mention', text: `${actorLabel} mentioned you`, to };
    case 'follow':
      return { kind: 'follow', text: `${actorLabel} followed you`, to };
    case 'dm':
      return { kind: 'message', text: `${actorLabel} sent you a message`, to };
    case 'mod_action':
      return { kind: 'mod', text: `A moderator acted on your ${n.target_type ?? 'content'}`, to };
    default:
      return { kind: 'other', text: `${actorLabel} interacted with your content`, to };
  }
}

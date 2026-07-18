import type { Notification } from './types';

export interface FormattedNotification {
  icon: string;
  text: string;
  to: string | null;
}

const ACTOR_FALLBACK = 'Someone';

export function formatNotification(n: Notification): FormattedNotification {
  const actor = n.actor_username ?? ACTOR_FALLBACK;
  const actorLabel = n.actor_username ? `u/${actor}` : actor;

  switch (n.verb) {
    case 'comment':
      return {
        icon: '💬',
        text: `${actorLabel} commented on your post`,
        to: n.target_type === 'post' && n.target_id ? `/posts/${n.target_id}` : null,
      };
    case 'reply':
      return {
        icon: '↪',
        text: `${actorLabel} replied to your comment`,
        to: null,
      };
    case 'mention':
      return {
        icon: '@',
        text: `${actorLabel} mentioned you`,
        to: n.target_type === 'post' && n.target_id ? `/posts/${n.target_id}` : null,
      };
    case 'follow':
      return {
        icon: '★',
        text: `${actorLabel} followed you`,
        to: n.actor_username ? `/u/${n.actor_username}` : null,
      };
    case 'vote':
      return {
        icon: '↑',
        text: `${actorLabel} upvoted your ${n.target_type ?? 'post'}`,
        to: n.target_type === 'post' && n.target_id ? `/posts/${n.target_id}` : null,
      };
    case 'dm':
      return {
        icon: '✉',
        text: `${actorLabel} sent you a message`,
        to: '/messages',
      };
    case 'mod_action':
      return {
        icon: '⚑',
        text: `A moderator acted on your ${n.target_type ?? 'content'}`,
        to: n.target_type === 'post' && n.target_id ? `/posts/${n.target_id}` : null,
      };
    default:
      return {
        icon: '•',
        text: `${actorLabel} interacted with your content`,
        to: null,
      };
  }
}

import type { TFunction } from 'i18next';
import type { Notification } from './types';

export type NotificationKind = 'comment' | 'reply' | 'mention' | 'follow' | 'message' | 'mod' | 'other';

export interface FormattedNotification {
  kind: NotificationKind;
  text: string;
  to: string | null;
}

function targetKey(targetType: Notification['target_type']): string {
  if (targetType === 'post') return 'notifications.target_post';
  if (targetType === 'comment') return 'notifications.target_comment';
  return 'notifications.target_content';
}

export function formatNotification(n: Notification, t: TFunction): FormattedNotification {
  const actor = n.actor_username ? `u/${n.actor_username}` : t('notifications.someone');
  const to = n.link;

  switch (n.verb) {
    case 'comment':
      return { kind: 'comment', text: t('notifications.comment', { actor }), to };
    case 'reply':
      return { kind: 'reply', text: t('notifications.reply', { actor }), to };
    case 'mention':
      return { kind: 'mention', text: t('notifications.mention', { actor }), to };
    case 'follow':
      return { kind: 'follow', text: t('notifications.follow', { actor }), to };
    case 'dm':
      return { kind: 'message', text: t('notifications.message', { actor }), to };
    case 'mod_action':
      return { kind: 'mod', text: t('notifications.mod', { target: t(targetKey(n.target_type)) }), to };
    default:
      return { kind: 'other', text: t('notifications.other', { actor }), to };
  }
}

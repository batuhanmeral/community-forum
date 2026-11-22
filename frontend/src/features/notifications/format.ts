import type { TFunction } from 'i18next';
import type { Notification } from './types';

export type NotificationKind = 'comment' | 'reply' | 'mention' | 'follow' | 'message' | 'mod' | 'answer' | 'bounty' | 'other';

export interface FormattedNotification {
  kind: NotificationKind;
  text: string;
  to: string | null;
  /** Server-sanitized HTML (removal reason body). */
  detailHtml?: string;
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
    case 'answer_accepted':
      return { kind: 'answer', text: t('notifications.answerAccepted'), to };
    case 'bounty_awarded':
      return { kind: 'bounty', text: t('notifications.bountyAwarded'), to };
    case 'bounty_refunded':
      return { kind: 'bounty', text: t('notifications.bountyRefunded'), to };
    case 'modmail':
      return { kind: 'mod', text: t('notifications.modmail'), to };
    case 'removal':
      return {
        kind: 'mod',
        text: t('notifications.removal', {
          target: t(targetKey(n.target_type)),
          reason: n.reason_title ?? '',
        }),
        to,
        detailHtml: n.reason_body_html || undefined,
      };
    default:
      return { kind: 'other', text: t('notifications.other', { actor }), to };
  }
}

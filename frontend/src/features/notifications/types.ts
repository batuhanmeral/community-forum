export type NotificationVerb =
  | 'comment'
  | 'reply'
  | 'mention'
  | 'follow'
  | 'dm'
  | 'mod_action'
  | 'answer_accepted'
  | 'bounty_awarded'

export type NotificationTargetType = 'post' | 'comment' | 'user' | string | null;

export interface Notification {
  id: number;
  recipient: number;
  actor: number | null;
  actor_username: string | null;
  verb: NotificationVerb;
  target_type: NotificationTargetType;
  target_id: number | null;
  link: string | null;
  created_at: string;
  read_at: string | null;
  reason_title?: string;
  reason_body_html?: string;
}

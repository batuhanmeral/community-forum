export type NotificationVerb =
  | 'comment'
  | 'reply'
  | 'mention'
  | 'follow'
  | 'vote'
  | 'dm'
  | 'mod_action';

export type NotificationTargetType = 'post' | 'comment' | 'user' | string | null;

export interface Notification {
  id: number;
  recipient: number;
  actor: number | null;
  actor_username: string | null;
  verb: NotificationVerb;
  target_type: NotificationTargetType;
  target_id: number | null;
  created_at: string;
  read_at: string | null;
}

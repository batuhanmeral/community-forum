export interface DMUser {
  id: number;
  username: string;
}

export interface Message {
  id: number;
  conversation: number;
  sender: number;
  sender_username: string;
  body: string;
  created_at: string;
  read_at: string | null;
}

export interface Conversation {
  id: number;
  participant_a: number;
  participant_b: number;
  other: DMUser | null;
  last_message: Message | null;
  unread_count: number;
  created_at: string;
}

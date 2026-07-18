import { api } from './client';
import type { Paginated } from '@/features/communities/types';
import type { Conversation, Message } from '@/features/messaging/types';

export async function listConversations(): Promise<Conversation[]> {
  const res = await api.get<Conversation[] | Paginated<Conversation>>('/conversations/');
  return Array.isArray(res.data) ? res.data : res.data.results;
}

export async function startConversation(username: string): Promise<Conversation> {
  const res = await api.post<Conversation>('/conversations/', { username });
  return res.data;
}

export async function listMessages(
  conversationId: number,
  page = 1,
): Promise<Paginated<Message>> {
  const res = await api.get<Paginated<Message>>(`/conversations/${conversationId}/messages/`, {
    params: { page },
  });
  return res.data;
}

export async function sendMessage(conversationId: number, body: string): Promise<Message> {
  const res = await api.post<Message>(`/conversations/${conversationId}/messages/`, { body });
  return res.data;
}

export async function markConversationRead(conversationId: number): Promise<void> {
  await api.post(`/conversations/${conversationId}/read/`);
}

import { api } from './client';
import type { Poll } from '@/features/posts/types';

export async function votePoll(pollId: number, optionId: number): Promise<Poll> {
  const res = await api.post<Poll>(`/polls/${pollId}/vote/`, { option_id: optionId });
  return res.data;
}

import { api } from './client';

export type VoteTarget = 'post' | 'comment';
export type VoteValue = 1 | -1;

export interface VoteResponse {
  user_vote: VoteValue | null;
}

export async function castVote(
  target: VoteTarget,
  objectId: number,
  value: VoteValue,
): Promise<VoteResponse> {
  const res = await api.post<VoteResponse>('/vote/', {
    content_type: target,
    object_id: objectId,
    value,
  });
  return res.data;
}

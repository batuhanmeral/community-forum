import { describe, expect, it, vi } from 'vitest';

vi.mock('./client', () => ({
  api: {
    get: vi.fn().mockResolvedValue({ data: {} }),
    post: vi.fn().mockResolvedValue({ data: {} }),
    patch: vi.fn().mockResolvedValue({ data: {} }),
    delete: vi.fn().mockResolvedValue({ data: {} }),
  },
}));

import { api } from './client';
import { followUser, listFollowers, listFollowing, unfollowUser, blockUser, unblockUser } from './follow';
import { banUser, setMemberRole, unbanUser } from './moderation';
import { getUserComments, getUserPosts, getUserProfile } from './users';

const RAW = 'we ird/name';
const ENCODED = 'we%20ird%2Fname';

type Method = 'get' | 'post' | 'patch' | 'delete';
const cases: [string, Method, () => Promise<unknown>][] = [
  ['getUserProfile', 'get', () => getUserProfile(RAW)],
  ['getUserPosts', 'get', () => getUserPosts(RAW)],
  ['getUserComments', 'get', () => getUserComments(RAW)],
  ['followUser', 'post', () => followUser(RAW)],
  ['unfollowUser', 'delete', () => unfollowUser(RAW)],
  ['listFollowers', 'get', () => listFollowers(RAW)],
  ['listFollowing', 'get', () => listFollowing(RAW)],
  ['blockUser', 'post', () => blockUser(RAW)],
  ['unblockUser', 'delete', () => unblockUser(RAW)],
  ['banUser', 'post', () => banUser('c', RAW)],
  ['unbanUser', 'delete', () => unbanUser('c', RAW)],
  ['setMemberRole', 'patch', () => setMemberRole('c', RAW, 'member')],
];

describe('username path segments', () => {
  it.each(cases)('%s encodes the username', async (_name, method, call) => {
    vi.mocked(api[method]).mockClear();
    await call();
    const url = vi.mocked(api[method]).mock.calls[0][0] as string;
    expect(url).toContain(ENCODED);
    expect(url).not.toContain(RAW);
  });
});

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer from '@/features/auth/authSlice';
import type { Community } from '@/features/communities/types';
import { HomeRightSidebar } from './HomeRightSidebar';
import * as trendingApi from '@/api/trending';
import * as usersApi from '@/api/users';

vi.mock('@/api/trending', () => ({
  trendingCommunities: vi.fn(),
  trendingPosts: vi.fn(),
}));
vi.mock('@/api/communities', () => ({ joinCommunity: vi.fn(), leaveCommunity: vi.fn() }));
vi.mock('@/api/users', () => ({ getLeaderboard: vi.fn() }));

const community: Community = {
  id: 1,
  slug: 'py',
  name: 'Py',
  description: '',
  avatar: null,
  is_nsfw: false,
  requires_approval: false,
  creator: 9,
  created_at: '2026-10-01T00:00:00Z',
  member_count: 1,
  is_member: false,
  is_banned: false,
  my_role: null,
};

function renderSidebar() {
  const store = configureStore({ reducer: { auth: authReducer } });
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <HomeRightSidebar />
      </MemoryRouter>
    </Provider>,
  );
}

describe('HomeRightSidebar community rows', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(trendingApi.trendingPosts).mockResolvedValue([]);
    vi.mocked(usersApi.getLeaderboard).mockResolvedValue([]);
  });

  it('shows a banned badge instead of a join button', async () => {
    vi.mocked(trendingApi.trendingCommunities).mockResolvedValue([{ ...community, is_banned: true }]);
    renderSidebar();
    expect(await screen.findByText('Banned')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Join' })).not.toBeInTheDocument();
  });

  it('offers join to everyone else', async () => {
    vi.mocked(trendingApi.trendingCommunities).mockResolvedValue([community]);
    renderSidebar();
    expect(await screen.findByRole('button', { name: 'Join' })).toBeInTheDocument();
  });
});

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer, { setUser } from '@/features/auth/authSlice';
import type { Community } from '@/features/communities/types';
import { CommunityDetailPage } from './CommunityDetailPage';
import * as communitiesApi from '@/api/communities';
import * as postsApi from '@/api/posts';

vi.mock('@/api/communities', () => ({
  getCommunity: vi.fn(),
  joinCommunity: vi.fn(),
  leaveCommunity: vi.fn(),
  listRules: vi.fn(),
  updateNotifyLevel: vi.fn(),
}));

vi.mock('@/api/posts', () => ({
  listCommunityPosts: vi.fn(),
}));

const baseCommunity: Community = {
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

function renderPage() {
  const store = configureStore({ reducer: { auth: authReducer } });
  store.dispatch(
    setUser({
      id: 1,
      username: 'alice',
      email: 'a@x.com',
      email_verified: true,
      avatar: null,
      bio: '',
      show_nsfw: false,
      post_karma: 0,
      comment_karma: 0,
    }),
  );
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/c/py']}>
        <Routes>
          <Route path="/c/:slug" element={<CommunityDetailPage />} />
        </Routes>
      </MemoryRouter>
    </Provider>,
  );
}

describe('CommunityDetailPage membership state', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(communitiesApi.listRules).mockResolvedValue([]);
    vi.mocked(postsApi.listCommunityPosts).mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    });
  });

  it('shows a banned badge instead of a join button for banned users', async () => {
    vi.mocked(communitiesApi.getCommunity).mockResolvedValue({ ...baseCommunity, is_banned: true });
    renderPage();
    expect(await screen.findByText('Banned')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Join' })).not.toBeInTheDocument();
  });

  it('offers join to everyone else', async () => {
    vi.mocked(communitiesApi.getCommunity).mockResolvedValue(baseCommunity);
    renderPage();
    expect(await screen.findByRole('button', { name: 'Join' })).toBeInTheDocument();
  });
});

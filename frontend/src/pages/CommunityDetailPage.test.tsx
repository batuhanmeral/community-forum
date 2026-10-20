import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer, { setUser } from '@/features/auth/authSlice';
import membershipsReducer from '@/features/communities/membershipsSlice';
import type { Community } from '@/features/communities/types';
import type { Post } from '@/features/posts/types';
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
  my_notify_level: null,
};

function renderPage() {
  const store = configureStore({
    reducer: { auth: authReducer, memberships: membershipsReducer },
  });
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

const post = (id: number): Post => ({
  id,
  author: 9,
  author_username: 'owner',
  community: 'py',
  flair: null,
  flair_detail: null,
  kind: 'text',
  title: `post ${id}`,
  body: '',
  body_html: '',
  is_deleted: false,
  url: '',
  image: null,
  is_nsfw: false,
  is_pinned: false,
  is_approved: true,
  score: 0,
  comment_count: 0,
  user_vote: null,
  is_saved: false,
  poll: null,
  created_at: '2026-10-01T00:00:00Z',
  edited_at: null,
});

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

  it('shows the stored notification level', async () => {
    vi.mocked(communitiesApi.getCommunity).mockResolvedValue({
      ...baseCommunity,
      is_member: true,
      my_role: 'member',
      my_notify_level: 'posts_only',
    });
    renderPage();
    expect(await screen.findByText('Posts only')).toBeInTheDocument();
  });

  it('loads more posts on demand', async () => {
    vi.mocked(communitiesApi.getCommunity).mockResolvedValue(baseCommunity);
    vi.mocked(postsApi.listCommunityPosts)
      .mockResolvedValueOnce({ count: 2, next: 'p2', previous: null, results: [post(1)] })
      .mockResolvedValueOnce({ count: 2, next: null, previous: 'p1', results: [post(2)] });
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: 'Load more posts' }));
    expect(await screen.findByText('post 2')).toBeInTheDocument();
    expect(postsApi.listCommunityPosts).toHaveBeenLastCalledWith('py', { sort: 'hot', page: 2 });
  });

  it('keeps the button and shows an error when loading more fails', async () => {
    vi.mocked(communitiesApi.getCommunity).mockResolvedValue(baseCommunity);
    vi.mocked(postsApi.listCommunityPosts)
      .mockResolvedValueOnce({ count: 2, next: 'p2', previous: null, results: [post(1)] })
      .mockRejectedValueOnce(new Error('boom'));
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: 'Load more posts' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load more posts.');
    expect(screen.getByRole('button', { name: 'Load more posts' })).toBeInTheDocument();
  });

  it('discards a load-more response that arrives after the sort changed', async () => {
    vi.mocked(communitiesApi.getCommunity).mockResolvedValue(baseCommunity);
    let resolveMore: (v: Awaited<ReturnType<typeof postsApi.listCommunityPosts>>) => void = () => {};
    vi.mocked(postsApi.listCommunityPosts)
      .mockResolvedValueOnce({ count: 2, next: 'p2', previous: null, results: [post(1)] })
      .mockReturnValueOnce(new Promise((res) => (resolveMore = res)))
      .mockResolvedValueOnce({ count: 1, next: null, previous: null, results: [post(3)] });
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: 'Load more posts' }));
    await userEvent.click(screen.getByRole('button', { name: /new/i }));
    expect(await screen.findByText('post 3')).toBeInTheDocument();
    resolveMore({ count: 2, next: null, previous: null, results: [post(2)] });
    await new Promise((r) => setTimeout(r, 0));
    expect(screen.queryByText('post 2')).not.toBeInTheDocument();
  });
});

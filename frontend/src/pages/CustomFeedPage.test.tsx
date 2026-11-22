import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer, { setUser } from '@/features/auth/authSlice';
import type { Post } from '@/features/posts/types';
import { CustomFeedPage } from './CustomFeedPage';
import * as feedsApi from '@/api/customFeeds';

vi.mock('@/api/customFeeds', () => ({ getFeed: vi.fn(), listFeedPosts: vi.fn(), deleteFeed: vi.fn() }));
vi.mock('@/api/votes', () => ({ castVote: vi.fn() }));
vi.mock('@/api/saves', () => ({ toggleSave: vi.fn() }));
vi.mock('@/api/posts', () => ({ hidePost: vi.fn(), unhidePost: vi.fn() }));

const feed: feedsApi.CustomFeed = {
  id: 1,
  name: 'Dev news',
  slug: 'dev-news',
  description: 'Things to read',
  is_public: true,
  owner_username: 'owner',
  communities: ['js', 'py'],
  created: '2026-10-01T00:00:00Z',
};

const post = {
  id: 7,
  author: 2,
  author_username: 'bob',
  community: 'py',
  flair: null,
  flair_detail: null,
  kind: 'text',
  title: 'Feed post',
  body: 'b',
  body_html: '<p>b</p>',
  is_deleted: false,
  url: '',
  image: null,
  is_nsfw: false,
  crosspost_from: null,
  is_spoiler: false,
  is_question: false,
  accepted_comment: null,
  bounty_amount: 0,
  bounty_expires_at: null,
  bounty_status: '',
  is_pinned: false,
  is_approved: true,
  score: 0,
  comment_count: 0,
  user_vote: null,
  is_saved: false,
  poll: null,
  created_at: '2026-10-01T00:00:00Z',
  edited_at: null,
} as Post;

function renderPage(me?: string) {
  const store = configureStore({ reducer: { auth: authReducer } });
  if (me) {
    store.dispatch(
      setUser({
        id: 1,
        username: me,
        email: 'a@x.com',
        email_verified: true,
        avatar: null,
        bio: '',
        country: '',
        show_nsfw: false,
        post_karma: 0,
        comment_karma: 0,
      }),
    );
  }
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/u/owner/feeds/dev-news']}>
        <Routes>
          <Route path="/u/:username/feeds/:slug" element={<CustomFeedPage />} />
          <Route path="/feeds" element={<p>manage page</p>} />
        </Routes>
      </MemoryRouter>
    </Provider>,
  );
}

describe('CustomFeedPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(feedsApi.getFeed).mockResolvedValue(feed);
    vi.mocked(feedsApi.listFeedPosts).mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [post],
    });
  });

  it('shows the feed, its communities and posts read-only for a visitor', async () => {
    renderPage();
    expect(await screen.findByRole('heading', { name: 'Dev news' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'c/js' })).toHaveAttribute('href', '/c/js');
    expect(await screen.findByText('Feed post')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Delete' })).toBeNull();
    expect(feedsApi.listFeedPosts).toHaveBeenCalledWith('owner', 'dev-news', { sort: 'new', page: 1 });
  });

  it('reloads posts when the sort changes', async () => {
    renderPage();
    await screen.findByText('Feed post');
    await userEvent.click(screen.getByRole('button', { name: 'Top' }));
    expect(feedsApi.listFeedPosts).toHaveBeenLastCalledWith('owner', 'dev-news', { sort: 'top', page: 1 });
  });

  it('shows not found for a missing or private feed', async () => {
    vi.mocked(feedsApi.getFeed).mockRejectedValue(new Error('404'));
    renderPage();
    expect(await screen.findByText('This feed does not exist or is private.')).toBeInTheDocument();
  });

  it('lets the owner delete the feed', async () => {
    vi.mocked(feedsApi.deleteFeed).mockResolvedValue();
    renderPage('owner');
    await userEvent.click(await screen.findByRole('button', { name: 'Delete' }));
    expect(feedsApi.deleteFeed).toHaveBeenCalledWith('owner', 'dev-news');
    expect(await screen.findByText('manage page')).toBeInTheDocument();
  });
});

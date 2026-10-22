import { afterEach, describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
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
import i18n from '@/i18n';
import { resetLanguage, visibleText } from '@/test/i18nHelpers';

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

describe('CommunityDetailPage in Turkish', () => {
  const ENGLISH_PROBE =
    /\b(Loading|not found|doesn't exist|Browse communities|Mod tools|Joined|Join|members?|Community rules|Create post|No posts|Hot|New|Top|All updates|Posts only|Muted|Notification level|Load more)\b/;

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(communitiesApi.listRules).mockResolvedValue([{ id: 1, short: 'Be kind', description: '', order: 1 }] as never);
    vi.mocked(postsApi.listCommunityPosts).mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
  });
  afterEach(resetLanguage);

  it('renders no English in Turkish for a moderator who has joined', async () => {
    vi.mocked(communitiesApi.getCommunity).mockResolvedValue({
      ...baseCommunity,
      is_member: true,
      my_role: 'moderator',
      my_notify_level: 'posts_only',
    });
    await i18n.changeLanguage('tr');
    renderPage();
    expect(await screen.findByText('Bu toplulukta henüz gönderi yok.')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Bildirim düzeyi' }));
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
  });

  it('renders no English in Turkish for a visitor with more posts', async () => {
    vi.mocked(communitiesApi.getCommunity).mockResolvedValue(baseCommunity);
    vi.mocked(postsApi.listCommunityPosts).mockResolvedValue({ count: 1, next: 'p2', previous: null, results: [post(1)] });
    await i18n.changeLanguage('tr');
    renderPage();
    await screen.findByText('post 1');
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
  });

  it('renders no English in Turkish for a missing community and while loading', async () => {
    vi.mocked(communitiesApi.getCommunity).mockRejectedValue(new Error('404'));
    await i18n.changeLanguage('tr');
    renderPage();
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
    expect(await screen.findByText('Topluluk bulunamadı')).toBeInTheDocument();
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
  });
});

describe('CommunityDetailPage title', () => {
  it('sets the page title while the community is loading', async () => {
    vi.mocked(communitiesApi.getCommunity).mockReturnValue(new Promise(() => undefined));
    renderPage();
    await waitFor(() => expect(document.title).toBe('Nexus'));
  });

  it('sets the page title to c/<slug>', async () => {
    vi.mocked(communitiesApi.getCommunity).mockResolvedValue(baseCommunity);
    vi.mocked(communitiesApi.listRules).mockResolvedValue([]);
    vi.mocked(postsApi.listCommunityPosts).mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    renderPage();
    await waitFor(() => expect(document.title).toBe('c/py · Nexus'));
  });
});

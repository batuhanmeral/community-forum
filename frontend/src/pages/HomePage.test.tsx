import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer, { setUser } from '@/features/auth/authSlice';
import type { Community } from '@/features/communities/types';
import type { Post } from '@/features/posts/types';
import { HomePage, type FeedVariant } from './HomePage';
import i18n from '@/i18n';
import { resetLanguage, visibleText } from '@/test/i18nHelpers';
import * as communitiesApi from '@/api/communities';
import * as postsApi from '@/api/posts';

vi.mock('@/api/communities', () => ({ listCommunities: vi.fn() }));
vi.mock('@/api/posts', () => ({ listFeed: vi.fn(), listFollowingFeed: vi.fn() }));
vi.mock('@/api/users', () => ({ updatePreferences: vi.fn() }));

const communities = vi.mocked(communitiesApi);
const posts = vi.mocked(postsApi);

const joined: Community = {
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
  is_member: true,
  is_banned: false,
  my_role: 'member',
  my_notify_level: 'all',
};

function renderHome({ authed = true, variant }: { authed?: boolean; variant?: FeedVariant } = {}) {
  const store = configureStore({ reducer: { auth: authReducer } });
  if (authed) {
    store.dispatch(
      setUser({
        id: 1,
        username: 'alice',
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
      <MemoryRouter>
        <HomePage variant={variant} />
      </MemoryRouter>
    </Provider>,
  );
}

const renderAuthed = () => renderHome();

const textPost = {
  id: 7,
  author: 9,
  author_username: 'bob',
  community: 'py',
  flair: null,
  flair_detail: null,
  kind: 'text',
  title: 'A post',
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
} as unknown as Post;

describe('HomePage create post button', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    posts.listFeed.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    communities.listCommunities.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
  });

  it('sits in the feed header for signed-in users as an icon', async () => {
    renderAuthed();
    const link = await screen.findByRole('link', { name: 'Create post' });
    expect(link).toHaveAttribute('href', '/submit');
    expect(link).toHaveTextContent('');
  });

  // The time range sits just left of the create button, and the inline composer is gone.
  it('puts an icon-only time range before it and drops the composer', async () => {
    renderAuthed();
    const link = await screen.findByRole('link', { name: 'Create post' });
    const range = screen.getByRole('button', { name: 'Time range: All time' });
    expect(range).toHaveTextContent('');
    expect(range.compareDocumentPosition(link) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.queryByText(/on your mind/)).not.toBeInTheDocument();
  });

  // Sort tabs sit right before the time range; the feed title is for screen readers only.
  it('orders sort, time range and plus, with no visible feed title', async () => {
    renderAuthed();
    const link = await screen.findByRole('link', { name: 'Create post' });
    const hot = screen.getByRole('button', { name: 'Hot' });
    const range = screen.getByRole('button', { name: 'Time range: All time' });
    expect(hot.compareDocumentPosition(range) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(range.compareDocumentPosition(link) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByRole('heading', { level: 1, name: 'Your feed' })).toHaveClass('sr-only');
    expect(screen.queryByText(/^\d+ communit/)).not.toBeInTheDocument();
  });

  it('is hidden from signed-out readers', async () => {
    renderHome({ authed: false });
    await screen.findByText(/No posts yet/);
    expect(screen.queryByRole('link', { name: 'Create post' })).not.toBeInTheDocument();
  });
});

describe('HomePage in Turkish', () => {
  const ENGLISH_PROBE =
    /\b(Hot|New|Top|Popular|All posts|Discussion|Media|Links?|Polls?|Image|Following|Your feed|Home|Show NSFW|Hide NSFW|community|communities|empty|following anyone|Discover users|Browse communities|Be the first|match this filter|Load more|Loading|What's on your mind|Create post)\b/;

  beforeEach(() => {
    vi.clearAllMocks();
    communities.listCommunities.mockResolvedValue({ count: 3, next: null, previous: null, results: [joined] });
    posts.listFeed.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    posts.listFollowingFeed.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
  });
  afterEach(resetLanguage);

  it('renders no English in Turkish for the empty personal feed', async () => {
    await i18n.changeLanguage('tr');
    renderHome();
    await waitFor(() => expect(posts.listFeed).toHaveBeenCalled());
    expect(await screen.findByText(/Akışın boş/)).toBeInTheDocument();
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
  });

  it('renders no English in Turkish on the following tab', async () => {
    await i18n.changeLanguage('tr');
    renderHome();
    await userEvent.click(await screen.findByRole('button', { name: 'Takip' }));
    expect(await screen.findByText(/kimseyi takip etmiyorsun/)).toBeInTheDocument();
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
  });

  it('renders no English in Turkish for a signed-out reader on every variant', async () => {
    await i18n.changeLanguage('tr');
    for (const variant of ['home', 'popular', 'all'] as const) {
      const { unmount } = renderHome({ authed: false, variant });
      await waitFor(() => expect(posts.listFeed).toHaveBeenCalled());
      expect(await screen.findByText(/İlk katkıyı sen yap/)).toBeInTheDocument();
      expect(visibleText()).not.toMatch(ENGLISH_PROBE);
      unmount();
    }
  });

  it('renders no English in Turkish with posts, a filter miss and more pages', async () => {
    posts.listFeed.mockResolvedValue({ count: 1, next: 'p2', previous: null, results: [textPost] });
    await i18n.changeLanguage('tr');
    renderHome();
    await screen.findByText('A post');
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
    await userEvent.click(screen.getByRole('button', { name: /Anketler/ }));
    expect(await screen.findByText(/filtreye uyan gönderi yok/)).toBeInTheDocument();
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
  });
});

describe('HomePage title', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    communities.listCommunities.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    posts.listFeed.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
  });

  it('sets the page title', async () => {
    renderHome({ authed: false });
    await waitFor(() => expect(posts.listFeed).toHaveBeenCalled());
    expect(document.title).toBe('Nexus');
  });

  it('titles the popular and all variants', async () => {
    const { unmount } = renderHome({ authed: false, variant: 'popular' });
    await waitFor(() => expect(document.title).toBe('Popular · Nexus'));
    unmount();
    renderHome({ authed: false, variant: 'all' });
    await waitFor(() => expect(document.title).toBe('All posts · Nexus'));
  });
});

describe('HomePage heading', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    communities.listCommunities.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    posts.listFeed.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
  });

  it('shows no slash route suffix on any variant', async () => {
    for (const variant of ['home', 'popular', 'all'] as const) {
      const { unmount } = renderHome({ authed: false, variant });
      await waitFor(() => expect(posts.listFeed).toHaveBeenCalled());
      expect(visibleText()).not.toMatch(/\/ (home|popular|all)\b/);
      unmount();
    }
  });
});

describe('HomePage time range', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    communities.listCommunities.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    posts.listFeed.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
  });

  it('refetches the feed for the chosen time range', async () => {
    renderHome({ authed: false });
    await waitFor(() => expect(posts.listFeed).toHaveBeenCalledWith(expect.objectContaining({ t: 'all' })));
    await userEvent.click(screen.getByRole('button', { name: 'Time range: All time' }));
    await userEvent.click(screen.getByRole('menuitemradio', { name: 'Past week' }));
    await waitFor(() =>
      expect(posts.listFeed).toHaveBeenLastCalledWith(expect.objectContaining({ t: 'week', page: 1 })),
    );
    expect(screen.getByRole('button', { name: 'Time range: Past week' })).toBeInTheDocument();
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });
});

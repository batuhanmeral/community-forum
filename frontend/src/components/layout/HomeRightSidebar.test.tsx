import { afterEach, describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer from '@/features/auth/authSlice';
import membershipsReducer from '@/features/communities/membershipsSlice';
import type { Community } from '@/features/communities/types';
import type { Post } from '@/features/posts/types';
import type { UserProfile } from '@/api/users';
import { HomeRightSidebar } from './HomeRightSidebar';
import * as trendingApi from '@/api/trending';
import * as usersApi from '@/api/users';
import i18n from '@/i18n';
import { resetLanguage, visibleText } from '@/test/i18nHelpers';

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
  my_notify_level: null,
};

function renderSidebar() {
  const store = configureStore({
    reducer: { auth: authReducer, memberships: membershipsReducer },
  });
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

describe('HomeRightSidebar in Turkish', () => {
  const ENGLISH_PROBE =
    /\b(Trending now|Hot|pts|See all|Top communities|Karma leaders|Create a community|Join|Joined|members?|Banned|No trending|No active)\b/;

  beforeEach(() => vi.clearAllMocks());
  afterEach(resetLanguage);

  it('renders no English in Turkish with data', async () => {
    await i18n.changeLanguage('tr');
    vi.mocked(trendingApi.trendingPosts).mockResolvedValue([
      { id: 1, title: 'Hello', community: 'py', score: 3, created_at: '2026-10-01T00:00:00Z' } as Post,
    ]);
    vi.mocked(trendingApi.trendingCommunities).mockResolvedValue([community, { ...community, id: 2, slug: 'go', is_banned: true }]);
    vi.mocked(usersApi.getLeaderboard).mockResolvedValue([{ id: 3, username: 'alice', total_karma: 5 } as UserProfile]);
    renderSidebar();
    await screen.findByText('Hello');
    await screen.findByText('c/go');
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
  });

  it('renders no English in Turkish when empty', async () => {
    await i18n.changeLanguage('tr');
    vi.mocked(trendingApi.trendingPosts).mockResolvedValue([]);
    vi.mocked(trendingApi.trendingCommunities).mockResolvedValue([]);
    renderSidebar();
    await screen.findByText(i18n.t('rightbar.noTrending'));
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
  });

  it('pluralises the member count', async () => {
    vi.mocked(trendingApi.trendingPosts).mockResolvedValue([]);
    vi.mocked(trendingApi.trendingCommunities).mockResolvedValue([community, { ...community, id: 2, slug: 'go', member_count: 1500 }]);
    renderSidebar();
    expect(await screen.findByText('1 member')).toBeInTheDocument();
    expect(screen.getByText('1.5k members')).toBeInTheDocument();
  });
});
describe('HomeRightSidebar layout', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(trendingApi.trendingPosts).mockResolvedValue([]);
    vi.mocked(trendingApi.trendingCommunities).mockResolvedValue([]);
    vi.mocked(usersApi.getLeaderboard).mockResolvedValue([]);
  });

  // AppLayout's column owns visibility (shown from 960 px); an own breakpoint left it empty at 960–1023 px.
  it('leaves visibility to the layout column', async () => {
    renderSidebar();
    await screen.findByText('No trending posts yet.');
    const aside = screen.getByRole('complementary');
    expect(aside).toHaveClass('flex');
    expect(aside).not.toHaveClass('hidden');
    expect(aside.className).not.toMatch(/\blg:/);
  });

  it('keeps cards at full height so the sidebar scrolls instead of clipping them', async () => {
    renderSidebar();
    await screen.findByText('No trending posts yet.');
    const cards = [...screen.getByRole('complementary').children].filter((el) => el.classList.contains('overflow-hidden'));
    expect(cards.length).toBeGreaterThan(0);
    for (const card of cards) expect(card).toHaveClass('shrink-0');
  });
});

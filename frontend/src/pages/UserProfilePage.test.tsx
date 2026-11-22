import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer, { setUser } from '@/features/auth/authSlice';
import { UserProfilePage } from './UserProfilePage';
import * as usersApi from '@/api/users';
import i18n from '@/i18n';
import { resetLanguage, visibleText } from '@/test/i18nHelpers';

vi.mock('@/api/users', () => ({
  getUserProfile: vi.fn(),
  getUserPosts: vi.fn(),
  getUserComments: vi.fn(),
  updateProfile: vi.fn(),
}));
vi.mock('@/api/follow', () => ({
  blockUser: vi.fn(),
  unblockUser: vi.fn(),
  followUser: vi.fn(),
  unfollowUser: vi.fn(),
  listFollowers: vi.fn(),
  listFollowing: vi.fn(),
}));

const api = vi.mocked(usersApi);

const me = {
  id: 1,
  username: 'alice',
  email: 'a@x.com',
  email_verified: true,
  avatar: null,
  bio: 'hi',
  country: '',
  show_nsfw: false,
  post_karma: 0,
  comment_karma: 0,
};
const empty = { count: 0, next: null, previous: null, results: [] };

async function openEditModal() {
  api.getUserProfile.mockResolvedValue({
    ...me,
    date_joined: '2026-01-01T00:00:00Z',
    total_karma: 0,
    followers_count: 0,
    following_count: 0,
    is_following: false,
    is_blocked: false,
  });
  api.getUserPosts.mockResolvedValue(empty);
  api.getUserComments.mockResolvedValue(empty);
  const store = configureStore({ reducer: { auth: authReducer } });
  store.dispatch(setUser(me));
  render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/u/alice']}>
        <Routes>
          <Route path="/u/:username" element={<UserProfilePage />} />
        </Routes>
      </MemoryRouter>
    </Provider>,
  );
  await userEvent.click(await screen.findByRole('button', { name: 'Edit profile' }));
}

describe('ProfileEditModal', () => {
  beforeEach(() => vi.clearAllMocks());

  it('shows the bio error under the field', async () => {
    api.updateProfile.mockRejectedValue({
      response: { status: 400, data: { bio: ['Bio is too long.'] } },
    });
    await openEditModal();
    await userEvent.click(screen.getByRole('button', { name: 'Save' }));
    const message = await screen.findByText('Bio is too long.');
    expect(screen.getByLabelText('Bio')).toHaveAttribute('aria-describedby', message.id);
    expect(screen.queryByText(/Could not save your profile/)).not.toBeInTheDocument();
  });

  it('falls back to a generic message without field errors', async () => {
    api.updateProfile.mockRejectedValue(new Error('network'));
    await openEditModal();
    await userEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(await screen.findByText(/Could not save your profile/)).toBeInTheDocument();
  });

  it('saves the chosen country with the profile', async () => {
    api.updateProfile.mockResolvedValue({ ...me, country: 'TR' });
    await openEditModal();
    await userEvent.selectOptions(screen.getByLabelText('Country'), 'TR');
    await userEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() =>
      expect(api.updateProfile).toHaveBeenCalledWith({ bio: 'hi', country: 'TR', avatar: null }),
    );
    expect(await screen.findByText('Türkiye')).toBeInTheDocument();
  });
});

describe('UserProfilePage', () => {
  const ENGLISH_PROBE =
    /\b(Joined|Edit profile|Block|Unblock|Report user|Total karma|Post karma|Comment karma|Followers|Following|posts|comments|Loading|has no|User not found|No user named|Upload avatar|Tell the community|Cancel|Save|Bio|Country|Not shown|Germany)\b/;

  beforeEach(() => {
    vi.clearAllMocks();
    api.getUserPosts.mockResolvedValue(empty);
    api.getUserComments.mockResolvedValue(empty);
  });

  afterEach(resetLanguage);

  function renderProfile(viewer: typeof me | null, username = 'bob') {
    const store = configureStore({ reducer: { auth: authReducer } });
    if (viewer) store.dispatch(setUser(viewer));
    return render(
      <Provider store={store}>
        <MemoryRouter initialEntries={[`/u/${username}`]}>
          <Routes>
            <Route path="/u/:username" element={<UserProfilePage />} />
          </Routes>
        </MemoryRouter>
      </Provider>,
    );
  }

  const bob = {
    ...me,
    id: 2,
    username: 'bob',
    date_joined: '2026-01-01T00:00:00Z',
    total_karma: 0,
    followers_count: 0,
    following_count: 0,
    is_following: false,
    is_blocked: false,
  };

  it('renders no English in Turkish', async () => {
    await i18n.changeLanguage('tr');
    api.getUserProfile.mockResolvedValue({ ...bob, country: 'DE' });
    renderProfile(me);
    expect(await screen.findByText('Almanya')).toBeInTheDocument();
    expect(screen.getByText('🇩🇪')).toHaveAttribute('aria-hidden', 'true');
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
    await screen.findByText(/henüz gönderi paylaşmadı/);
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
    await userEvent.click(screen.getByRole('button', { name: 'Kullanıcıyı bildir' }));
    expect(visibleText()).toMatch(/Kullanıcıyı bildir/);
    expect(visibleText()).not.toMatch(/Report user|Report user\b/);
  });

  it('renders the edit modal and the missing-user card in Turkish', async () => {
    await i18n.changeLanguage('tr');
    api.getUserProfile.mockResolvedValue({ ...bob, ...me });
    renderProfile(me, 'alice');
    await userEvent.click(await screen.findByRole('button', { name: 'Profili düzenle' }));
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
    await resetLanguage();
    await i18n.changeLanguage('tr');
    api.getUserProfile.mockRejectedValue(new Error('404'));
    renderProfile(null, 'ghost');
    expect(await screen.findByText('Kullanıcı bulunamadı')).toBeInTheDocument();
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
  });

  it('masks inline spoilers in the comment list', async () => {
    api.getUserProfile.mockResolvedValue(bob);
    api.getUserComments.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: 8,
          post: 3,
          author: 2,
          author_username: 'bob',
          author_avatar: null,
          parent: null,
          body: 'It was >!the butler!< again',
          body_html: '',
          is_deleted: false,
          is_accepted: false,
          score: 0,
          user_vote: null,
          is_saved: false,
          created_at: '2026-10-01T00:00:00Z',
          updated_at: '2026-10-01T00:00:00Z',
          edited_at: null,
        },
      ],
    });
    renderProfile(null);
    await userEvent.click(await screen.findByRole('button', { name: 'Comments' }));
    expect(await screen.findByText('It was [spoiler] again')).toBeInTheDocument();
    expect(visibleText()).not.toMatch(/butler/);
  });

  it('shows a deleted comment body in Turkish in the comment list', async () => {
    await i18n.changeLanguage('tr');
    api.getUserProfile.mockResolvedValue(bob);
    api.getUserComments.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: 7,
          post: 3,
          author: null,
          author_username: null,
          author_avatar: null,
          parent: null,
          body: '[deleted]',
          body_html: '<p>[deleted]</p>',
          is_deleted: true,
          is_accepted: false,
          score: 0,
          user_vote: null,
          is_saved: false,
          created_at: '2026-10-01T00:00:00Z',
          updated_at: '2026-10-01T00:00:00Z',
          edited_at: null,
        },
      ],
    });
    renderProfile(null);
    await userEvent.click(await screen.findByRole('button', { name: 'Yorumlar' }));
    expect(await screen.findByText('[silindi]')).toBeInTheDocument();
    expect(visibleText()).not.toMatch(/\[(deleted|removed)\]/);
  });

  it.each([
    ['while loading', 'bob', () => new Promise<typeof bob>(() => undefined), 'Nexus'],
    ['for a missing user', 'ghost', () => Promise.reject(new Error('404')), 'User not found · Nexus'],
    ['for an existing user', 'bob', async () => bob, 'u/bob · Nexus'],
  ] as const)('sets the page title %s', async (_state, username, getUserProfile, expected) => {
    api.getUserProfile.mockImplementation(getUserProfile);
    renderProfile(null, username);
    await waitFor(() => expect(document.title).toBe(expected));
  });
});

describe('karma stats', () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => vi.clearAllMocks());

  function renderWith(karma: { post_karma: number; comment_karma: number; bounty_held: number }) {
    api.getUserProfile.mockResolvedValue({
      ...me,
      ...karma,
      date_joined: '2026-01-01T00:00:00Z',
      total_karma: karma.post_karma + karma.comment_karma,
      followers_count: 0,
      following_count: 0,
      is_following: false,
      is_blocked: false,
    });
    api.getUserPosts.mockResolvedValue(empty);
    api.getUserComments.mockResolvedValue(empty);
    const store = configureStore({ reducer: { auth: authReducer } });
    render(
      <Provider store={store}>
        <MemoryRouter initialEntries={['/u/alice']}>
          <Routes>
            <Route path="/u/:username" element={<UserProfilePage />} />
          </Routes>
        </MemoryRouter>
      </Provider>,
    );
  }

  it('shows a bounty hold separately instead of as negative comment karma', async () => {
    renderWith({ post_karma: 150, comment_karma: -50, bounty_held: 50 });
    const label = await screen.findByText('Comment karma');
    expect(label.previousElementSibling?.textContent).toBe('0');
    expect(screen.getByText('50 held in bounties')).toBeInTheDocument();
    expect(screen.getByText('100')).toBeInTheDocument();
  });

  it('still shows genuinely negative comment karma', async () => {
    renderWith({ post_karma: 10, comment_karma: -20, bounty_held: 0 });
    const label = await screen.findByText('Comment karma');
    expect(label.previousElementSibling?.textContent).toBe('-20');
    expect(screen.queryByText(/held in bounties/)).toBeNull();
  });
});

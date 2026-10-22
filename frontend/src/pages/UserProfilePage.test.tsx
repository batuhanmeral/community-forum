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
});

describe('UserProfilePage', () => {
  const ENGLISH_PROBE =
    /\b(Joined|Edit profile|Block|Unblock|Report user|Total karma|Post karma|Comment karma|Followers|Following|posts|comments|Loading|has no|User not found|No user named|Upload avatar|Tell the community|Cancel|Save|Bio)\b/;

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
    api.getUserProfile.mockResolvedValue(bob);
    renderProfile(me);
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

  it('sets the page title to u/<username>', async () => {
    api.getUserProfile.mockResolvedValue(bob);
    renderProfile(null);
    await waitFor(() => expect(document.title).toBe('u/bob · Nexus'));
  });
});

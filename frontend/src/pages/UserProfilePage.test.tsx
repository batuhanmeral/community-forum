import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer, { setUser } from '@/features/auth/authSlice';
import { UserProfilePage } from './UserProfilePage';
import * as usersApi from '@/api/users';

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

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer, { setUser } from '@/features/auth/authSlice';
import { SettingsPage } from './SettingsPage';
import * as usersApi from '@/api/users';
import * as followApi from '@/api/follow';

vi.mock('@/api/users', () => ({
  changePassword: vi.fn(),
  deactivateAccount: vi.fn(),
  updatePreferences: vi.fn(),
}));

vi.mock('@/api/follow', () => ({
  listBlocked: vi.fn(),
  unblockUser: vi.fn(),
}));

const changePassword = vi.mocked(usersApi.changePassword);
const listBlocked = vi.mocked(followApi.listBlocked);
const unblockUser = vi.mocked(followApi.unblockUser);

const testUser = {
  id: 1,
  username: 'alice',
  email: 'a@x.com',
  email_verified: true,
  avatar: null,
  bio: '',
  show_nsfw: false,
  post_karma: 0,
  comment_karma: 0,
};

function renderPage() {
  const store = configureStore({ reducer: { auth: authReducer } });
  store.dispatch(setUser(testUser));
  return {
    store,
    ...render(
      <Provider store={store}>
        <MemoryRouter>
          <SettingsPage />
        </MemoryRouter>
      </Provider>,
    ),
  };
}

describe('SettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listBlocked.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    changePassword.mockResolvedValue({ access: 'new-access', refresh: 'new-refresh' });
    unblockUser.mockResolvedValue();
  });

  it('rejects mismatched new passwords without calling the API', async () => {
    renderPage();
    await userEvent.type(screen.getByLabelText(/current password/i), 'old-pass');
    await userEvent.type(screen.getByLabelText(/^new password$/i), 'new-pass-1');
    await userEvent.type(screen.getByLabelText(/confirm new password/i), 'different');
    await userEvent.click(screen.getByRole('button', { name: /update password/i }));

    expect(await screen.findByText(/do not match/i)).toBeInTheDocument();
    expect(changePassword).not.toHaveBeenCalled();
  });

  it('stores the rotated token pair after a password change', async () => {
    const { store } = renderPage();
    await userEvent.type(screen.getByLabelText(/current password/i), 'old-pass');
    await userEvent.type(screen.getByLabelText(/^new password$/i), 'new-pass-1');
    await userEvent.type(screen.getByLabelText(/confirm new password/i), 'new-pass-1');
    await userEvent.click(screen.getByRole('button', { name: /update password/i }));

    await waitFor(() => expect(store.getState().auth.accessToken).toBe('new-access'));
    expect(store.getState().auth.refreshToken).toBe('new-refresh');
  });

  it('submits a valid password change and clears the form', async () => {
    renderPage();
    await userEvent.type(screen.getByLabelText(/current password/i), 'old-pass');
    await userEvent.type(screen.getByLabelText(/^new password$/i), 'new-pass-1');
    await userEvent.type(screen.getByLabelText(/confirm new password/i), 'new-pass-1');
    await userEvent.click(screen.getByRole('button', { name: /update password/i }));

    await waitFor(() => expect(changePassword).toHaveBeenCalledWith('old-pass', 'new-pass-1'));
    expect(await screen.findByText(/password updated/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/current password/i)).toHaveValue('');
  });

  it('surfaces API validation errors', async () => {
    changePassword.mockRejectedValueOnce({
      response: { data: { current_password: ['Current password is incorrect.'] } },
    });
    renderPage();
    await userEvent.type(screen.getByLabelText(/current password/i), 'wrong');
    await userEvent.type(screen.getByLabelText(/^new password$/i), 'new-pass-1');
    await userEvent.type(screen.getByLabelText(/confirm new password/i), 'new-pass-1');
    await userEvent.click(screen.getByRole('button', { name: /update password/i }));

    expect(await screen.findByText(/current password is incorrect/i)).toBeInTheDocument();
  });

  it('lists blocked users and unblocks on click', async () => {
    listBlocked.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [{ id: 2, username: 'bob', avatar: null, is_following: false }],
    });
    renderPage();
    expect(await screen.findByText('u/bob')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /unblock/i }));
    await waitFor(() => expect(unblockUser).toHaveBeenCalledWith('bob'));
    expect(screen.queryByText('u/bob')).not.toBeInTheDocument();
  });

  it('asks for confirmation before deactivating', async () => {
    renderPage();
    await userEvent.click(screen.getByRole('button', { name: /deactivate account/i }));
    expect(screen.getByRole('button', { name: /yes, deactivate/i })).toBeInTheDocument();
    expect(vi.mocked(usersApi.deactivateAccount)).not.toHaveBeenCalled();
  });
});

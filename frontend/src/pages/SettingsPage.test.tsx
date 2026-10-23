import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer, { setUser } from '@/features/auth/authSlice';
import { SettingsPage } from './SettingsPage';
import * as usersApi from '@/api/users';
import * as followApi from '@/api/follow';
import i18n from '@/i18n';
import { resetLanguage, visibleText } from '@/test/i18nHelpers';

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

describe('SettingsPage in Turkish', () => {
  const ENGLISH_PROBE =
    /\b(Show NSFW|Applies everywhere|Change password|Current password|New password|Confirm new|Update password|Blocked users|Unblock|blocked anyone|Danger zone|Deactivat\w*|Cancel|Loading|do not match)\b/;

  beforeEach(() => {
    vi.clearAllMocks();
    listBlocked.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
  });

  afterEach(resetLanguage);

  it('renders no English in Turkish', async () => {
    await i18n.changeLanguage('tr');
    renderPage();
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
    await screen.findByText(/engellemedin/);
    await userEvent.click(screen.getByRole('button', { name: /hesabı devre dışı bırak/i }));
    await userEvent.type(screen.getByLabelText('Mevcut parola'), 'old-pass-1');
    await userEvent.type(screen.getByLabelText('Yeni parola'), 'new-pass-1');
    await userEvent.type(screen.getByLabelText('Yeni parolayı doğrula'), 'new-pass-2');
    await userEvent.click(screen.getByRole('button', { name: 'Parolayı güncelle' }));
    expect(await screen.findByText('Yeni parolalar eşleşmiyor.')).toBeInTheDocument();
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
  });

  it('sets the page title', async () => {
    renderPage();
    await waitFor(() => expect(document.title).toBe('Settings · Nexus'));
    await act(() => i18n.changeLanguage('tr'));
    await waitFor(() => expect(document.title).toBe('Ayarlar · Nexus'));
  });
});

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { AxiosError, type AxiosResponse } from 'axios';
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
  deleteAccount: vi.fn(),
  downloadAccountExport: vi.fn(),
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
    changePassword.mockResolvedValue({ access: 'new-access' });
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

  it('stores the new access token after a password change', async () => {
    const { store } = renderPage();
    await userEvent.type(screen.getByLabelText(/current password/i), 'old-pass');
    await userEvent.type(screen.getByLabelText(/^new password$/i), 'new-pass-1');
    await userEvent.type(screen.getByLabelText(/confirm new password/i), 'new-pass-1');
    await userEvent.click(screen.getByRole('button', { name: /update password/i }));

    await waitFor(() => expect(store.getState().auth.accessToken).toBe('new-access'));
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

  it('asks for the password before deleting the account', async () => {
    renderPage();
    await userEvent.click(screen.getByRole('button', { name: /^delete account$/i }));
    const confirm = screen.getByRole('button', { name: /delete my account permanently/i });
    expect(confirm).toBeDisabled();
    expect(vi.mocked(usersApi.deleteAccount)).not.toHaveBeenCalled();
  });

  it('deletes the account with the password and signs out', async () => {
    vi.mocked(usersApi.deleteAccount).mockResolvedValue();
    const { store } = renderPage();
    localStorage.setItem('nexus.session', '1');
    await userEvent.click(screen.getByRole('button', { name: /^delete account$/i }));
    await userEvent.type(screen.getByLabelText(/confirm with your password/i), 'pw-123');
    await userEvent.click(screen.getByRole('button', { name: /delete my account permanently/i }));
    await waitFor(() => expect(store.getState().auth.user).toBeNull());
    expect(vi.mocked(usersApi.deleteAccount)).toHaveBeenCalledWith('pw-123');
    expect(localStorage.getItem('nexus.session')).toBeNull();
  });

  it('sends the deletion outside the cross-tab lock so a refresh can still run', async () => {
    const order: string[] = [];
    vi.mocked(usersApi.deleteAccount).mockImplementation(async () => {
      order.push('delete');
    });
    const request = vi.fn(async (_name: string, fn: () => Promise<unknown>) => {
      order.push('lock');
      return fn();
    });
    Object.defineProperty(navigator, 'locks', { configurable: true, value: { request } });
    try {
      const { store } = renderPage();
      await userEvent.click(screen.getByRole('button', { name: /^delete account$/i }));
      await userEvent.type(screen.getByLabelText(/confirm with your password/i), 'pw-123');
      await userEvent.click(screen.getByRole('button', { name: /delete my account permanently/i }));
      await waitFor(() => expect(store.getState().auth.user).toBeNull());
      expect(order).toEqual(['delete', 'lock']);
    } finally {
      delete (navigator as { locks?: unknown }).locks;
    }
  });

  it('keeps the account and says why when the password is wrong', async () => {
    vi.mocked(usersApi.deleteAccount).mockRejectedValue(
      new AxiosError('bad', '400', undefined, undefined, { status: 400 } as AxiosResponse),
    );
    const { store } = renderPage();
    await userEvent.click(screen.getByRole('button', { name: /^delete account$/i }));
    await userEvent.type(screen.getByLabelText(/confirm with your password/i), 'nope');
    await userEvent.click(screen.getByRole('button', { name: /delete my account permanently/i }));
    expect(await screen.findByText('Password is incorrect.')).toBeInTheDocument();
    expect(store.getState().auth.user).not.toBeNull();
  });

  it('downloads the data export as a JSON file', async () => {
    vi.mocked(usersApi.downloadAccountExport).mockResolvedValue(new Blob(['{}']));
    const createObjectURL = vi.fn(() => 'blob:x');
    const revokeObjectURL = vi.fn();
    Object.assign(URL, { createObjectURL, revokeObjectURL });
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    renderPage();
    await userEvent.click(screen.getByRole('button', { name: /download my data/i }));
    await waitFor(() => expect(click).toHaveBeenCalled());
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:x');
    click.mockRestore();
  });

  it('explains when the export fails', async () => {
    vi.mocked(usersApi.downloadAccountExport).mockRejectedValue(new Error('down'));
    renderPage();
    await userEvent.click(screen.getByRole('button', { name: /download my data/i }));
    expect(await screen.findByText(/could not prepare the download/i)).toBeInTheDocument();
  });
});

describe('SettingsPage in Turkish', () => {
  const ENGLISH_PROBE =
    /\b(Show NSFW|Applies everywhere|Change password|Current password|New password|Confirm new|Update password|Blocked users|Unblock|blocked anyone|Danger zone|Delete account|Download my data|Your data|Cancel|Loading|do not match)\b/;

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
    await userEvent.click(screen.getByRole('button', { name: /^hesabı sil$/i }));
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

describe('SettingsPage theme', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    listBlocked.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    vi.stubGlobal('matchMedia', () => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
  });

  afterEach(() => vi.unstubAllGlobals());

  it('switches to the light theme and remembers it', async () => {
    renderPage();
    await userEvent.selectOptions(screen.getByRole('combobox', { name: /theme/i }), 'light');
    expect(document.documentElement.dataset.theme).toBe('light');
    expect(localStorage.getItem('nexus.theme')).toBe('light');
  });
});

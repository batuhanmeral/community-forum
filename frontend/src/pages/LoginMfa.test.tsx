import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer from '@/features/auth/authSlice';
import '@/i18n';
import { LoginPage } from './LoginPage';
import * as authApi from '@/api/auth';

vi.mock('@/api/auth', async (orig) => ({
  ...(await orig<typeof import('@/api/auth')>()),
  login: vi.fn(),
  verifyMfa: vi.fn(),
  fetchMe: vi.fn(),
}));
vi.mock('@/api/client', () => ({
  withAuthLock: (fn: () => Promise<unknown>) => fn(),
  api: {},
  AUTH_REQUEST_TIMEOUT_MS: 1000,
}));

function renderLogin() {
  const store = configureStore({ reducer: { auth: authReducer } });
  render(
    <Provider store={store}>
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    </Provider>,
  );
  return store;
}

async function passwordStep() {
  await userEvent.type(screen.getByLabelText('Username'), 'alice');
  await userEvent.type(screen.getByLabelText('Password'), 'secret-pass');
  await userEvent.click(screen.getByRole('button', { name: 'Log in' }));
}

beforeEach(() => vi.resetAllMocks());

describe('login with two-step verification', () => {
  it('asks for the code instead of starting a session, then completes the login', async () => {
    vi.mocked(authApi.login).mockResolvedValue({ mfa_required: true, mfa_token: 'tok' });
    vi.mocked(authApi.verifyMfa).mockResolvedValue({ access: 'a.b.c' });
    vi.mocked(authApi.fetchMe).mockResolvedValue({ id: 1, username: 'alice' } as never);
    const store = renderLogin();
    await passwordStep();
    expect(await screen.findByLabelText('Code')).toBeInTheDocument();
    expect(store.getState().auth.accessToken).toBeNull();
    expect(authApi.fetchMe).not.toHaveBeenCalled();
    await userEvent.type(screen.getByLabelText('Code'), '123456');
    await userEvent.click(screen.getByRole('button', { name: 'Verify' }));
    await waitFor(() => expect(authApi.verifyMfa).toHaveBeenCalledWith('tok', '123456'));
    await waitFor(() => expect(authApi.fetchMe).toHaveBeenCalled());
  });

  it('starts over from the password when the code is refused', async () => {
    vi.mocked(authApi.login).mockResolvedValue({ mfa_required: true, mfa_token: 'tok' });
    vi.mocked(authApi.verifyMfa).mockRejectedValue({ response: { status: 401 } });
    renderLogin();
    await passwordStep();
    await userEvent.type(await screen.findByLabelText('Code'), '000000');
    await userEvent.click(screen.getByRole('button', { name: 'Verify' }));
    expect(await screen.findByText(/not accepted/)).toBeInTheDocument();
    expect(screen.getByLabelText('Password')).toBeInTheDocument();
  });

  it('tells a locked-out user to wait', async () => {
    vi.mocked(authApi.login).mockResolvedValue({ mfa_required: true, mfa_token: 'tok' });
    vi.mocked(authApi.verifyMfa).mockRejectedValue({ response: { status: 429 } });
    renderLogin();
    await passwordStep();
    await userEvent.type(await screen.findByLabelText('Code'), '000000');
    await userEvent.click(screen.getByRole('button', { name: 'Verify' }));
    expect(await screen.findByText(/Too many failed attempts/)).toBeInTheDocument();
  });
});

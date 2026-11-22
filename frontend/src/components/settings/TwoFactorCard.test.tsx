import { beforeEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer from '@/features/auth/authSlice';
import '@/i18n';
import { TwoFactorCard } from './TwoFactorCard';
import * as users from '@/api/users';

vi.mock('@/api/users');

function renderCard() {
  const store = configureStore({ reducer: { auth: authReducer } });
  render(
    <Provider store={store}>
      <TwoFactorCard />
    </Provider>,
  );
}

const JWT = 'x.eyJ1c2VyX2lkIjoiMSJ9.y';

beforeEach(() => vi.resetAllMocks());

it('says so when the server has no encryption key', async () => {
  vi.mocked(users.getMfaStatus).mockResolvedValue({ available: false, enabled: false, recovery_codes_remaining: 0 });
  renderCard();
  expect(await screen.findByText(/not available on this server/)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Set up two-step verification' })).not.toBeInTheDocument();
});

it('walks through setup and shows the recovery codes once', async () => {
  vi.mocked(users.getMfaStatus).mockResolvedValue({ available: true, enabled: false, recovery_codes_remaining: 0 });
  vi.mocked(users.startMfaSetup).mockResolvedValue({
    secret: 'ABCDEF', otpauth_uri: 'otpauth://totp/x', qr_data_uri: 'data:image/svg+xml;base64,AAA',
  });
  vi.mocked(users.confirmMfa).mockResolvedValue({ access: JWT, recovery_codes: ['AAAAA-BBBBB', 'CCCCC-DDDDD'] });
  renderCard();
  await userEvent.click(await screen.findByRole('button', { name: 'Set up two-step verification' }));
  await userEvent.type(screen.getByLabelText('Current password'), 'pw');
  await userEvent.click(screen.getByRole('button', { name: 'Continue' }));
  expect(await screen.findByAltText('QR code for your authenticator app')).toBeInTheDocument();
  expect(screen.getByText('ABCDEF')).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText('Code from the app'), '123456');
  await userEvent.click(screen.getByRole('button', { name: 'Turn on' }));
  await waitFor(() => expect(users.confirmMfa).toHaveBeenCalledWith('123456'));
  expect(await screen.findByText('AAAAA-BBBBB')).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'I saved them' }));
  expect(screen.queryByText('AAAAA-BBBBB')).not.toBeInTheDocument();
  expect(screen.getByText(/Two-step verification is on/)).toBeInTheDocument();
});

it('needs password and code to turn it off', async () => {
  vi.mocked(users.getMfaStatus).mockResolvedValue({ available: true, enabled: true, recovery_codes_remaining: 7 });
  vi.mocked(users.disableMfa).mockResolvedValue({ access: JWT });
  renderCard();
  expect(await screen.findByText(/7 recovery codes left/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Turn off' }));
  const submit = screen.getAllByRole('button', { name: 'Turn off' }).at(-1)!;
  expect(submit).toBeDisabled();
  await userEvent.type(screen.getByLabelText('Current password'), 'pw');
  await userEvent.type(screen.getByLabelText('Authenticator or recovery code'), '123456');
  await userEvent.click(submit);
  await waitFor(() => expect(users.disableMfa).toHaveBeenCalledWith('pw', '123456'));
  expect(await screen.findByRole('button', { name: 'Set up two-step verification' })).toBeInTheDocument();
});

it('shows the lockout message', async () => {
  vi.mocked(users.getMfaStatus).mockResolvedValue({ available: true, enabled: true, recovery_codes_remaining: 7 });
  vi.mocked(users.regenerateRecoveryCodes).mockRejectedValue({ response: { status: 429 } });
  renderCard();
  await userEvent.click(await screen.findByRole('button', { name: 'Get new recovery codes' }));
  await userEvent.type(screen.getByLabelText('Current password'), 'pw');
  await userEvent.type(screen.getByLabelText('Authenticator or recovery code'), '1');
  await userEvent.click(screen.getAllByRole('button', { name: 'Get new recovery codes' }).at(-1)!);
  expect(await screen.findByRole('alert')).toHaveTextContent('Too many failed attempts');
});

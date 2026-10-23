import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer from '@/features/auth/authSlice';
import i18n from '@/i18n';
import { resetLanguage } from '@/test/i18nHelpers';
import { LoginPage } from './LoginPage';
import { RegisterPage } from './RegisterPage';
import { ForgotPasswordPage } from './ForgotPasswordPage';
import { ResetPasswordPage } from './ResetPasswordPage';
import { VerifyEmailPage } from './VerifyEmailPage';
import { NotFoundPage } from './NotFoundPage';

vi.mock('@/api/auth', () => ({
  login: vi.fn(),
  register: vi.fn(),
  fetchMe: vi.fn(),
  verifyEmail: vi.fn(() => new Promise(() => undefined)),
  requestPasswordReset: vi.fn(),
  confirmPasswordReset: vi.fn(),
}));

function renderPage(element: React.ReactElement, path = '/') {
  const store = configureStore({ reducer: { auth: authReducer } });
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={[path]}>{element}</MemoryRouter>
    </Provider>,
  );
}

const PAGES: Array<[string, React.ReactElement, string, string]> = [
  ['login', <LoginPage />, 'Log in · Nexus', 'Giriş yap · Nexus'],
  ['register', <RegisterPage />, 'Create account · Nexus', 'Hesap oluştur · Nexus'],
  ['forgot password', <ForgotPasswordPage />, 'Reset your password · Nexus', 'Parolanı sıfırla · Nexus'],
  ['reset password', <ResetPasswordPage />, 'Choose a new password · Nexus', 'Yeni bir parola belirle · Nexus'],
  ['verify email', <VerifyEmailPage />, 'Email verification · Nexus', 'E-posta doğrulama · Nexus'],
  ['not found', <NotFoundPage />, 'Page not found · Nexus', 'Sayfa bulunamadı · Nexus'],
];

describe('auth and fallback pages', () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(resetLanguage);

  it.each(PAGES)('%s sets the page title', async (_name, element, en, tr) => {
    renderPage(element);
    await waitFor(() => expect(document.title).toBe(en));
    await act(() => i18n.changeLanguage('tr'));
    await waitFor(() => expect(document.title).toBe(tr));
  });
});

describe('auth shell', () => {
  it.each([
    ['login', <LoginPage />],
    ['register', <RegisterPage />],
  ])('%s shows no brand block above the form', (_name, element) => {
    const { container } = renderPage(element);
    expect(container.querySelector('a[href="/"]')).toBeNull();
  });
});

import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { AxiosError } from 'axios';
import { useAppDispatch, useAppSelector } from '@/app/hooks';
import { authFailure, authIdle, authStart, setAccessToken, setUser } from '@/features/auth/authSlice';
import { fetchMe, login, needsSecondFactor, verifyMfa } from '@/api/auth';
import { withAuthLock } from '@/api/client';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { PageTitle } from '@/components/ui/PageTitle';

export function LoginPage() {
  const { t } = useTranslation();
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const location = useLocation();
  const { status, error } = useAppSelector((s) => s.auth);
  const isAuthed = useAppSelector((s) => s.auth.status === 'authenticated');

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [code, setCode] = useState('');

  if (isAuthed) {
    const from = (location.state as { from?: string } | null)?.from ?? '/';
    return <Navigate to={from} replace />;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    dispatch(authStart());
    try {
      // Under the refresh lock so another tab's refresh can't overwrite this login's cookie.
      let challenge: string | null = null;
      await withAuthLock(async () => {
        const result = mfaToken
          ? await verifyMfa(mfaToken, code.trim())
          : await login({ username, password });
        if (needsSecondFactor(result)) challenge = result.mfa_token;
        else dispatch(setAccessToken(result.access));
      });
      if (challenge) {
        // Password accepted; ask for the second factor before any session exists.
        setMfaToken(challenge);
        setPassword('');
        dispatch(authIdle());
        return;
      }
      const me = await fetchMe();
      dispatch(setUser(me));
      const from = (location.state as { from?: string } | null)?.from ?? '/';
      navigate(from, { replace: true });
    } catch (err) {
      const ax = err as AxiosError<{ detail?: string }>;
      const statusCode = ax.response?.status;
      if (mfaToken && statusCode === 401) {
        // The challenge is single use and may be burnt: start over from the password.
        setMfaToken(null);
        setCode('');
        dispatch(authFailure(t('auth.mfaFailed')));
        return;
      }
      if (mfaToken && statusCode === 429) {
        dispatch(authFailure(t('auth.mfaLocked')));
        return;
      }
      if (statusCode === 503) {
        dispatch(authFailure(t('auth.mfaUnavailable')));
        return;
      }
      dispatch(authFailure(ax.response?.data?.detail ?? t('auth.invalidCredentials')));
    }
  }

  if (mfaToken) {
    return (
      <AuthShell title={t('auth.mfaTitle')} subtitle={t('auth.mfaSubtitle')}>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <Input
            name="mfa-code"
            label={t('auth.mfaCode')}
            autoComplete="one-time-code"
            inputMode="text"
            autoFocus
            value={code}
            onChange={(e) => setCode(e.target.value)}
            required
          />
          <p className="text-xs text-[var(--color-text-muted)]">{t('auth.mfaRecoveryHint')}</p>
          {error && (
            <p role="alert" className="text-sm text-[var(--color-danger)]">
              {error}
            </p>
          )}
          <Button type="submit" loading={status === 'loading'} disabled={!code.trim()} fullWidth>
            {t('auth.mfaVerify')}
          </Button>
          <button
            type="button"
            onClick={() => {
              setMfaToken(null);
              setCode('');
              dispatch(authIdle());
            }}
            className="text-center text-sm text-[var(--color-text-muted)] hover:text-[var(--color-link)]"
          >
            {t('auth.mfaBack')}
          </button>
        </form>
      </AuthShell>
    );
  }

  return (
    <AuthShell title={t('auth.loginTitle')} subtitle={t('auth.loginSubtitle')}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Input
          name="username"
          label={t('auth.username')}
          autoComplete="username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
        />
        <Input
          name="password"
          type="password"
          label={t('auth.password')}
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        {error && <p className="text-sm text-[var(--color-danger)]">{error}</p>}
        <Button type="submit" loading={status === 'loading'} fullWidth>
          {t('auth.loginTitle')}
        </Button>
        <Link
          to="/forgot-password"
          className="text-center text-sm text-[var(--color-text-muted)] hover:text-[var(--color-link)]"
        >
          {t('auth.forgotPassword')}
        </Link>
      </form>
      <p className="mt-6 text-center text-sm text-[var(--color-text-muted)]">
        {t('auth.newToNexus')}{' '}
        <Link to="/register" className="font-medium text-[var(--color-link)] underline underline-offset-2 hover:text-[var(--color-link-hover)]">
          {t('auth.createAccount')}
        </Link>
      </p>
    </AuthShell>
  );
}

interface ShellProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}

export function AuthShell({ title, subtitle, children }: ShellProps) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--color-bg)] px-4 py-12">
      <PageTitle title={title} />
      <div className="w-full max-w-md">
        <div className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-7">
          <h1 className="text-2xl font-bold">{title}</h1>
          {subtitle && (
            <p className="mt-1 text-sm text-[var(--color-text-muted)]">{subtitle}</p>
          )}
          <div className="mt-6">{children}</div>
        </div>
      </div>
    </div>
  );
}

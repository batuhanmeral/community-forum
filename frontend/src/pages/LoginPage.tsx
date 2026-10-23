import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { AxiosError } from 'axios';
import { useAppDispatch, useAppSelector } from '@/app/hooks';
import { authFailure, authStart, setAccessToken, setUser } from '@/features/auth/authSlice';
import { fetchMe, login } from '@/api/auth';
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

  if (isAuthed) {
    const from = (location.state as { from?: string } | null)?.from ?? '/';
    return <Navigate to={from} replace />;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    dispatch(authStart());
    try {
      // Under the refresh lock so another tab's refresh can't overwrite this login's cookie.
      await withAuthLock(async () => {
        const tokens = await login({ username, password });
        dispatch(setAccessToken(tokens.access));
      });
      const me = await fetchMe();
      dispatch(setUser(me));
      const from = (location.state as { from?: string } | null)?.from ?? '/';
      navigate(from, { replace: true });
    } catch (err) {
      const ax = err as AxiosError<{ detail?: string }>;
      dispatch(authFailure(ax.response?.data?.detail ?? t('auth.invalidCredentials')));
    }
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

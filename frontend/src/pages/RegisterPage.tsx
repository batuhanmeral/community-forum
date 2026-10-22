import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { AxiosError } from 'axios';
import { useAppDispatch, useAppSelector } from '@/app/hooks';
import { authFailure, authStart, setTokens, setUser } from '@/features/auth/authSlice';
import { fetchMe, login, register } from '@/api/auth';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { AuthShell } from './LoginPage';

type FieldErrors = Partial<Record<'username' | 'email' | 'password' | 'non_field', string>>;

export function RegisterPage() {
  const { t } = useTranslation();
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const isAuthed = useAppSelector((s) => s.auth.status === 'authenticated');
  const status = useAppSelector((s) => s.auth.status);

  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});

  if (isAuthed) return <Navigate to="/" replace />;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setFieldErrors({});

    if (password !== confirm) {
      setFieldErrors({ password: t('auth.passwordsMismatch') });
      return;
    }

    dispatch(authStart());
    try {
      await register({ username, email, password });
      const tokens = await login({ username, password });
      dispatch(setTokens(tokens));
      const me = await fetchMe();
      dispatch(setUser(me));
      navigate('/', { replace: true });
    } catch (err) {
      const ax = err as AxiosError<Record<string, string[] | string>>;
      const data = ax.response?.data ?? {};
      const fe: FieldErrors = {};
      for (const [key, val] of Object.entries(data)) {
        const msg = Array.isArray(val) ? val[0] : String(val);
        if (key === 'username' || key === 'email' || key === 'password') fe[key] = msg;
        else fe.non_field = msg;
      }
      setFieldErrors(fe);
      dispatch(authFailure(fe.non_field ?? t('auth.registerFailed')));
    }
  }

  return (
    <AuthShell title={t('auth.registerTitle')} subtitle={t('auth.registerSubtitle')}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Input
          name="username"
          label={t('auth.username')}
          autoComplete="username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          error={fieldErrors.username}
          required
        />
        <Input
          name="email"
          type="email"
          label={t('auth.email')}
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={fieldErrors.email}
          required
        />
        <Input
          name="password"
          type="password"
          label={t('auth.password')}
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={fieldErrors.password}
          required
          minLength={8}
        />
        <Input
          name="confirm"
          type="password"
          label={t('auth.confirmPassword')}
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          required
        />
        {fieldErrors.non_field && (
          <p className="text-sm text-[var(--color-danger)]">{fieldErrors.non_field}</p>
        )}
        <Button type="submit" loading={status === 'loading'} fullWidth>
          {t('auth.registerTitle')}
        </Button>
      </form>
      <p className="mt-6 text-center text-sm text-[var(--color-text-muted)]">
        {t('auth.haveAccount')}{' '}
        <Link to="/login" className="font-medium text-[var(--color-accent)] hover:underline">
          {t('auth.loginInstead')}
        </Link>
      </p>
    </AuthShell>
  );
}

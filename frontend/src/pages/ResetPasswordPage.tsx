import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useSearchParams } from 'react-router-dom';
import { AxiosError } from 'axios';
import { confirmPasswordReset } from '@/api/auth';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { AuthShell } from './LoginPage';

export function ResetPasswordPage() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const uid = params.get('uid') ?? '';
  const token = params.get('token') ?? '';

  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const linkOk = Boolean(uid && token);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await confirmPasswordReset(uid, token, password);
      setDone(true);
    } catch (err) {
      const data = (err as AxiosError<Record<string, string[] | string>>).response?.data;
      const first = data && Object.values(data)[0];
      const text = Array.isArray(first) ? first[0] : first;
      setError(text ?? t('auth.resetInvalidLink'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell title={t('auth.resetTitle')}>
      {!linkOk ? (
        <p className="text-sm text-[var(--color-danger)]">{t('auth.resetInvalidLink')}</p>
      ) : done ? (
        <p className="text-sm text-[var(--color-success)]">{t('auth.resetDone')}</p>
      ) : (
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <Input
            name="new-password"
            type="password"
            label={t('auth.newPassword')}
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          {error && <p className="text-sm text-[var(--color-danger)]">{error}</p>}
          <Button type="submit" loading={busy} fullWidth>
            {t('auth.resetPassword')}
          </Button>
        </form>
      )}
      <p className="mt-6 text-center text-sm text-[var(--color-text-muted)]">
        <Link to="/login" className="font-medium text-[var(--color-accent)] hover:underline">
          {t('auth.backToLogin')}
        </Link>
      </p>
    </AuthShell>
  );
}

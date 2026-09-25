import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { requestPasswordReset } from '@/api/auth';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { AuthShell } from './LoginPage';

export function ForgotPasswordPage() {
  const { t } = useTranslation();
  const [email, setEmail] = useState('');
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    try {
      await requestPasswordReset(email.trim());
    } catch {
      // Same message either way: the endpoint never reveals account existence.
    } finally {
      setSent(true);
      setBusy(false);
    }
  }

  return (
    <AuthShell title={t('auth.forgotTitle')} subtitle={t('auth.forgotSubtitle')}>
      {sent ? (
        <p className="text-sm text-[var(--color-success)]">{t('auth.resetEmailSent')}</p>
      ) : (
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <Input
            name="email"
            type="email"
            label={t('auth.email')}
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <Button type="submit" loading={busy} fullWidth>
            {t('auth.sendResetLink')}
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

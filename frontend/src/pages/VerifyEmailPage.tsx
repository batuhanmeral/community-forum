import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useSearchParams } from 'react-router-dom';
import { verifyEmail } from '@/api/auth';
import { AuthShell } from './LoginPage';
import { APP_NAME } from '@/components/ui/PageTitle';
import { ArrowRight } from 'lucide-react';

type State = 'pending' | 'success' | 'failed' | 'missing';

export function VerifyEmailPage() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const [state, setState] = useState<State>('pending');

  useEffect(() => {
    const uid = params.get('uid');
    const token = params.get('token');
    if (!uid || !token) {
      setState('missing');
      return;
    }
    let cancelled = false;
    verifyEmail(uid, token)
      .then(() => {
        if (!cancelled) setState('success');
      })
      .catch(() => {
        if (!cancelled) setState('failed');
      });
    return () => {
      cancelled = true;
    };
  }, [params]);

  const message = {
    pending: <p className="text-sm text-[var(--color-text-muted)]">{t('auth.verifying')}</p>,
    success: <p className="text-sm text-[var(--color-success)]">{t('auth.verifySuccess')}</p>,
    failed: <p className="text-sm text-[var(--color-danger)]">{t('auth.verifyFailed')}</p>,
    missing: <p className="text-sm text-[var(--color-danger)]">{t('auth.verifyMissing')}</p>,
  }[state];

  return (
    <AuthShell title={t('auth.verifyTitle')}>
      {message}
      <p className="mt-6 text-center text-sm text-[var(--color-text-muted)]">
        <Link to="/" className="inline-flex items-center gap-1 font-medium text-[var(--color-accent)] hover:underline">
          {APP_NAME}
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </p>
    </AuthShell>
  );
}

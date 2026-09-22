import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/Button';

export function NotFoundPage() {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col items-center gap-4 py-24 text-center">
      <h1 className="text-5xl font-black tracking-tight">404</h1>
      <p className="text-[var(--color-text-muted)]">{t('notFound.lost')}</p>
      <Link to="/">
        <Button variant="primary">{t('notFound.takeMeHome')}</Button>
      </Link>
    </div>
  );
}

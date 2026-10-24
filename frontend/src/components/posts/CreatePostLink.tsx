import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Plus } from 'lucide-react';
import { cn } from '@/lib/cn';

export function CreatePostLink({ to, showLabel = false }: { to: string; showLabel?: boolean }) {
  const { t } = useTranslation();
  const label = t('feed.createPost');
  return (
    <Link
      to={to}
      title={showLabel ? undefined : label}
      aria-label={showLabel ? undefined : label}
      className={cn(
        'inline-flex h-10 items-center justify-center gap-1.5 rounded-[var(--radius-control)] bg-[var(--color-link)] text-[var(--color-on-link)] transition-colors hover:bg-[var(--color-link-hover)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-link)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg)]',
        showLabel ? 'px-3.5 text-[13px] font-semibold' : 'w-10',
      )}
    >
      <Plus strokeWidth={2.4} className="h-[18px] w-[18px]" />
      {showLabel && label}
    </Link>
  );
}

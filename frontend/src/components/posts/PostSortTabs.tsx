import { useTranslation } from 'react-i18next';
import type { SortOption } from '@/api/posts';
import { cn } from '@/lib/cn';

interface PostSortTabsProps {
  value: SortOption;
  onChange: (sort: SortOption) => void;
}

const SORTS: SortOption[] = ['hot', 'new', 'top'];

export function PostSortTabs({ value, onChange }: PostSortTabsProps) {
  const { t } = useTranslation();
  return (
    <div className="flex items-center gap-1 rounded-[var(--radius-control)] border border-[var(--color-border)] bg-[var(--color-surface)] p-1">
      {SORTS.map((sort) => (
        <button
          key={sort}
          type="button"
          onClick={() => onChange(sort)}
          className={cn(
            'rounded-[var(--radius-control-inner)] px-4 py-1.5 text-sm transition-colors',
            value === sort
              ? 'bg-[var(--color-bg-elevated)] text-[var(--color-text)]'
              : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]',
          )}
        >
          {t(`sort.${sort}`)}
        </button>
      ))}
    </div>
  );
}

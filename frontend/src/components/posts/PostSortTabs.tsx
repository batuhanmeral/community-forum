import { useTranslation } from 'react-i18next';
import type { SortOption } from '@/api/posts';
import { cn } from '@/lib/cn';
import { ArrowUpToLine, Clock, Flame } from 'lucide-react';

interface PostSortTabsProps {
  value: SortOption;
  onChange: (sort: SortOption) => void;
}

const SORT_TABS: { id: SortOption; icon: React.ReactNode }[] = [
  { id: 'hot', icon: <Flame className="h-[13px] w-[13px]" /> },
  { id: 'new', icon: <Clock className="h-[13px] w-[13px]" /> },
  { id: 'top', icon: <ArrowUpToLine className="h-[13px] w-[13px]" /> },
];

export function PostSortTabs({ value, onChange }: PostSortTabsProps) {
  const { t } = useTranslation();
  return (
    <div className="flex gap-0.5 rounded-[var(--radius-control)] border border-[var(--color-border)] bg-[var(--color-bg-1)] p-1">
      {SORT_TABS.map((tab) => (
        <button
          key={tab.id}
          type="button"
          onClick={() => onChange(tab.id)}
          className={cn(
            'inline-flex items-center gap-1.5 rounded-[var(--radius-control-inner)] px-3.5 py-1.5 text-[13px] font-medium transition max-sm:gap-1 max-sm:px-2',
            value === tab.id
              ? 'bg-[var(--color-bg-3)] text-[var(--color-text)]'
              : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]',
          )}
        >
          {tab.icon}
          {t(`sort.${tab.id}`)}
        </button>
      ))}
    </div>
  );
}

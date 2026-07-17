import type { SortOption } from '@/api/posts';
import { cn } from '@/lib/cn';

interface PostSortTabsProps {
  value: SortOption;
  onChange: (sort: SortOption) => void;
}

const tabs: Array<{ value: SortOption; label: string }> = [
  { value: 'hot', label: 'Hot' },
  { value: 'new', label: 'New' },
  { value: 'top', label: 'Top' },
];

export function PostSortTabs({ value, onChange }: PostSortTabsProps) {
  return (
    <div className="flex items-center gap-1 rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] p-1">
      {tabs.map((t) => (
        <button
          key={t.value}
          type="button"
          onClick={() => onChange(t.value)}
          className={cn(
            'rounded-full px-4 py-1.5 text-sm transition-colors',
            value === t.value
              ? 'bg-[var(--color-bg-elevated)] text-[var(--color-text)]'
              : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]',
          )}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

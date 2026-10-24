import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { TimeWindow } from '@/api/posts';
import { cn } from '@/lib/cn';
import { CalendarDays, Check, ChevronDown } from 'lucide-react';

const TIME_WINDOWS: TimeWindow[] = ['hour', 'day', 'week', 'month', 'year', 'all'];

interface TimeRangeSelectProps {
  value: TimeWindow;
  onChange: (value: TimeWindow) => void;
  /** Calendar icon only; the chosen range stays in the tooltip and label. */
  iconOnly?: boolean;
}

export function TimeRangeSelect({ value, onChange, iconOnly = false }: TimeRangeSelectProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const label = `${t('timeRange.label')}: ${t(`timeRange.${value}`)}`;

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative self-stretch">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={label}
        title={iconOnly ? label : undefined}
        className={cn(
          'inline-flex h-full min-h-10 items-center gap-1.5 rounded-[var(--radius-control)] border text-[13px] font-medium transition',
          iconOnly ? 'w-10 justify-center' : 'px-3',
          value === 'all'
            ? 'border-[var(--color-border)] bg-[var(--color-bg-1)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]'
            : 'border-[var(--color-link-border)] bg-[var(--color-link-dim)] text-[var(--color-link)]',
        )}
      >
        <CalendarDays className={iconOnly ? 'h-[17px] w-[17px]' : 'h-[14px] w-[14px]'} />
        {!iconOnly && (
          <>
            {t(`timeRange.${value}`)}
            <ChevronDown className="h-[14px] w-[14px] opacity-70" />
          </>
        )}
      </button>
      {open && (
        <div
          role="menu"
          className={cn(
            'absolute z-20 mt-1.5 w-44 overflow-hidden rounded-[var(--radius-control)] border border-[var(--color-border-strong)] bg-[var(--color-bg-elevated)] py-1 shadow-md',
            iconOnly ? 'right-0' : 'left-0',
          )}
        >
          {TIME_WINDOWS.map((w) => (
            <button
              key={w}
              type="button"
              role="menuitemradio"
              aria-checked={w === value}
              onClick={() => {
                onChange(w);
                setOpen(false);
              }}
              className={cn(
                'flex w-full items-center justify-between px-3 py-2 text-left text-[13px] hover:bg-[var(--color-surface-hover)]',
                w === value ? 'text-[var(--color-link)]' : 'text-[var(--color-text-soft)]',
              )}
            >
              {t(`timeRange.${w}`)}
              {w === value && <Check className="h-3.5 w-3.5" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

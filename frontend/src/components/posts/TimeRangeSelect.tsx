import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { TimeWindow } from '@/api/posts';
import { cn } from '@/lib/cn';
import { CalendarDays, Check, ChevronDown } from 'lucide-react';

const TIME_WINDOWS: TimeWindow[] = ['hour', 'day', 'week', 'month', 'year', 'all'];

interface TimeRangeSelectProps {
  value: TimeWindow;
  onChange: (value: TimeWindow) => void;
}

export function TimeRangeSelect({ value, onChange }: TimeRangeSelectProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

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
        aria-label={`${t('timeRange.label')}: ${t(`timeRange.${value}`)}`}
        className={cn(
          'inline-flex h-full items-center gap-1.5 rounded-[var(--radius-control)] border px-3 text-[13px] font-medium transition',
          value === 'all'
            ? 'border-[var(--color-border)] bg-[var(--color-bg-1)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]'
            : 'border-[var(--color-link-border)] bg-[var(--color-link-dim)] text-[var(--color-link)]',
        )}
      >
        <CalendarDays className="h-[14px] w-[14px]" />
        {t(`timeRange.${value}`)}
        <ChevronDown className="h-[14px] w-[14px] opacity-70" />
      </button>
      {open && (
        <div
          role="menu"
          className="absolute left-0 z-20 mt-1.5 w-44 overflow-hidden rounded-[var(--radius-control)] border border-[var(--color-border-strong)] bg-[var(--color-bg-elevated)] py-1 shadow-md"
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

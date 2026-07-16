import type { HTMLAttributes } from 'react';
import { cn } from '@/lib/cn';

type Tone = 'neutral' | 'accent' | 'danger' | 'success';

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
}

const toneClasses: Record<Tone, string> = {
  neutral:
    'bg-[var(--color-surface-hover)] text-[var(--color-text-muted)] border border-[var(--color-border)]',
  accent: 'bg-[var(--color-accent)]/15 text-[var(--color-accent)] border border-[var(--color-accent)]/30',
  danger: 'bg-[var(--color-danger)]/15 text-[var(--color-danger)] border border-[var(--color-danger)]/30',
  success: 'bg-[var(--color-success)]/15 text-[var(--color-success)] border border-[var(--color-success)]/30',
};

export function Badge({ tone = 'neutral', className, children, ...rest }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide',
        toneClasses[tone],
        className,
      )}
      {...rest}
    >
      {children}
    </span>
  );
}

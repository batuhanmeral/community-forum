import type { HTMLAttributes } from 'react';
import { cn } from '@/lib/cn';

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  padded?: boolean;
  interactive?: boolean;
}

export function Card({ padded = true, interactive, className, children, ...rest }: CardProps) {
  return (
    <div
      className={cn(
        'rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)]',
        padded && 'p-4',
        interactive && 'transition-colors hover:border-[var(--color-border-strong)] hover:bg-[var(--color-surface-hover)] cursor-pointer',
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  );
}

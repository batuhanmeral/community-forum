import { cn } from '@/lib/cn';

type Size = 'xs' | 'sm' | 'md' | 'lg';

interface AvatarProps {
  src?: string | null;
  alt?: string;
  size?: Size;
  className?: string;
}

const sizeClasses: Record<Size, string> = {
  xs: 'h-6 w-6 text-[10px]',
  sm: 'h-8 w-8 text-xs',
  md: 'h-10 w-10 text-sm',
  lg: 'h-16 w-16 text-lg',
};

function initials(name?: string): string {
  if (!name) return '?';
  return name.slice(0, 2).toUpperCase();
}

export function Avatar({ src, alt, size = 'md', className }: AvatarProps) {
  const base = cn(
    'inline-flex shrink-0 items-center justify-center overflow-hidden rounded-[var(--radius-avatar)]',
    'bg-[var(--color-surface-hover)] text-[var(--color-text-muted)] font-medium',
    'ring-1 ring-[var(--color-border)]',
    sizeClasses[size],
    className,
  );

  if (src) {
    return <img src={src} alt={alt ?? ''} className={base} />;
  }
  return <span className={base}>{initials(alt)}</span>;
}

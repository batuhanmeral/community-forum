import { useState, type MouseEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { toggleSave, type SaveTarget } from '@/api/saves';
import { useAppSelector } from '@/app/hooks';
import { cn } from '@/lib/cn';
import { Bookmark } from 'lucide-react';

interface SaveButtonProps {
  target: SaveTarget;
  objectId: number;
  initialSaved: boolean;
  size?: 'sm' | 'md';
  variant?: 'pill' | 'inline';
  onChange?: (saved: boolean) => void;
}

const bookmarkIcon = (filled: boolean) => (
  <Bookmark fill={filled ? 'currentColor' : 'none'} className="h-[15px] w-[15px]" />
);

export function SaveButton({
  target,
  objectId,
  initialSaved,
  size = 'md',
  variant = 'inline',
  onChange,
}: SaveButtonProps) {
  const navigate = useNavigate();
  const isAuthed = useAppSelector((s) => s.auth.status === 'authenticated');
  const [saved, setSaved] = useState(initialSaved);
  const [busy, setBusy] = useState(false);

  async function handleClick(e: MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (busy) return;
    if (!isAuthed) {
      navigate('/login');
      return;
    }
    const prev = saved;
    const next = !prev;
    setSaved(next);
    onChange?.(next);
    setBusy(true);
    try {
      const res = await toggleSave(target, objectId);
      if (res.is_saved !== next) {
        setSaved(res.is_saved);
        onChange?.(res.is_saved);
      }
    } catch {
      setSaved(prev);
      onChange?.(prev);
    } finally {
      setBusy(false);
    }
  }

  if (variant === 'inline') {
    return (
      <button
        type="button"
        onClick={handleClick}
        disabled={busy}
        className={cn(
          'inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[12.5px] font-medium transition disabled:opacity-60',
          saved
            ? 'bg-[var(--color-accent-dim)] text-[var(--color-accent)]'
            : 'bg-[var(--color-bg-elevated)] text-[var(--color-text-muted)] hover:bg-[var(--color-bg-3)] hover:text-[var(--color-text)]',
        )}
      >
        {bookmarkIcon(saved)}
        <span className="max-[480px]:hidden">{saved ? 'Saved' : 'Save'}</span>
      </button>
    );
  }

  const heightCls = size === 'sm' ? 'h-7 px-2.5 text-[11.5px]' : 'h-8 px-3 text-[12px]';
  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={busy}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border font-medium transition disabled:opacity-60',
        heightCls,
        saved
          ? 'border-[var(--color-accent)] bg-[var(--color-accent-dim)] text-[var(--color-accent)]'
          : 'border-[var(--color-border)] bg-[var(--color-bg-elevated)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]',
      )}
    >
      {bookmarkIcon(saved)}
      {saved ? 'Saved' : 'Save'}
    </button>
  );
}

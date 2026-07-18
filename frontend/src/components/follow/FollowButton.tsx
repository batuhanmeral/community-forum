import { useState, type MouseEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { followUser, unfollowUser } from '@/api/follow';
import { useAppSelector } from '@/app/hooks';
import { cn } from '@/lib/cn';

interface FollowButtonProps {
  username: string;
  initialFollowing: boolean;
  size?: 'sm' | 'md';
  onChange?: (following: boolean) => void;
}

export function FollowButton({ username, initialFollowing, size = 'md', onChange }: FollowButtonProps) {
  const navigate = useNavigate();
  const isAuthed = useAppSelector((s) => s.auth.status === 'authenticated');
  const myUsername = useAppSelector((s) => s.auth.user?.username);
  const [following, setFollowing] = useState(initialFollowing);
  const [busy, setBusy] = useState(false);

  // Hide on own profile
  if (myUsername && myUsername === username) return null;

  async function handleClick(e: MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (busy) return;
    if (!isAuthed) {
      navigate('/login');
      return;
    }
    const prev = following;
    const next = !prev;
    setFollowing(next);
    onChange?.(next);
    setBusy(true);
    try {
      if (next) await followUser(username);
      else await unfollowUser(username);
    } catch {
      setFollowing(prev);
      onChange?.(prev);
    } finally {
      setBusy(false);
    }
  }

  const heightCls = size === 'sm' ? 'h-7 px-3 text-[12px]' : 'h-9 px-4 text-[13px]';

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={busy}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border font-semibold tracking-tight transition disabled:opacity-60',
        heightCls,
        following
          ? 'border-[var(--color-border)] bg-transparent text-[var(--color-text-muted)] hover:border-[var(--color-danger)] hover:text-[var(--color-danger)]'
          : 'border-[var(--color-accent)] bg-[var(--color-accent)] text-[#061218] hover:opacity-90',
      )}
    >
      {following ? 'Following' : 'Follow'}
    </button>
  );
}

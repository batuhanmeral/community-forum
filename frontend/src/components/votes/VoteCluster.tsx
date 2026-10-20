import { useState, type MouseEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { castVote, type VoteTarget, type VoteValue } from '@/api/votes';
import { useAppSelector } from '@/app/hooks';
import { cn } from '@/lib/cn';
import { ArrowBigDown, ArrowBigUp } from 'lucide-react';

interface VoteClusterProps {
  target: VoteTarget;
  objectId: number;
  score: number;
  userVote: VoteValue | null;
  layout?: 'horizontal' | 'vertical';
  size?: 'sm' | 'md';
  onChange?: (next: { score: number; userVote: VoteValue | null }) => void;
}

export function VoteCluster({
  target,
  objectId,
  score,
  userVote,
  layout = 'horizontal',
  size = 'md',
  onChange,
}: VoteClusterProps) {
  const navigate = useNavigate();
  const isAuthed = useAppSelector((s) => s.auth.status === 'authenticated');
  const [localScore, setLocalScore] = useState(score);
  const [localVote, setLocalVote] = useState<VoteValue | null>(userVote);
  const [busy, setBusy] = useState(false);

  async function handle(value: VoteValue, e: MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (busy) return;
    if (!isAuthed) {
      navigate('/login');
      return;
    }

    const prevScore = localScore;
    const prevVote = localVote;

    // Optimistic toggle
    let nextVote: VoteValue | null;
    if (localVote === value) nextVote = null;
    else nextVote = value;

    const delta = (nextVote ?? 0) - (localVote ?? 0);
    const nextScore = localScore + delta;

    setLocalVote(nextVote);
    setLocalScore(nextScore);
    onChange?.({ score: nextScore, userVote: nextVote });
    setBusy(true);

    try {
      const res = await castVote(target, objectId, value);
      // Sync with server in case of drift
      if (res.user_vote !== nextVote) {
        setLocalVote(res.user_vote);
        const serverDelta = (res.user_vote ?? 0) - (prevVote ?? 0);
        const serverScore = prevScore + serverDelta;
        setLocalScore(serverScore);
        onChange?.({ score: serverScore, userVote: res.user_vote });
      }
    } catch {
      // Rollback
      setLocalVote(prevVote);
      setLocalScore(prevScore);
      onChange?.({ score: prevScore, userVote: prevVote });
    } finally {
      setBusy(false);
    }
  }

  const iconSize = size === 'sm' ? 13 : 15;
  const btnSize = size === 'sm' ? 'h-6 w-6' : 'h-7 w-7';
  const fontSize = size === 'sm' ? 'text-[12px]' : 'text-[13px]';

  if (layout === 'vertical') {
    return (
      <div className="flex flex-col items-center gap-0.5">
        <ArrowBtn
          direction="up"
          active={localVote === 1}
          size={iconSize}
          btnSize={btnSize}
          onClick={(e) => handle(1, e)}
        />
        <span
          className={cn(
            'font-mono font-medium tracking-tight',
            fontSize,
            localVote === 1 && 'text-[var(--color-accent)]',
            localVote === -1 && 'text-[var(--color-danger)]',
            localVote === null && 'text-[var(--color-text)]',
          )}
        >
          {formatScore(localScore)}
        </span>
        <ArrowBtn
          direction="down"
          active={localVote === -1}
          size={iconSize}
          btnSize={btnSize}
          onClick={(e) => handle(-1, e)}
        />
      </div>
    );
  }

  return (
    <div className="font-mono inline-flex items-center gap-0.5 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-1">
      <ArrowBtn
        direction="up"
        active={localVote === 1}
        size={iconSize}
        btnSize={btnSize}
        onClick={(e) => handle(1, e)}
      />
      <span
        className={cn(
          'min-w-[36px] text-center font-medium tracking-tight',
          fontSize,
          localVote === 1 && 'text-[var(--color-accent)]',
          localVote === -1 && 'text-[var(--color-danger)]',
          localVote === null && 'text-[var(--color-text)]',
        )}
      >
        {formatScore(localScore)}
      </span>
      <ArrowBtn
        direction="down"
        active={localVote === -1}
        size={iconSize}
        btnSize={btnSize}
        onClick={(e) => handle(-1, e)}
      />
    </div>
  );
}

interface ArrowBtnProps {
  direction: 'up' | 'down';
  active: boolean;
  size: number;
  btnSize: string;
  onClick: (e: MouseEvent) => void;
}

function ArrowBtn({ direction, active, size, btnSize, onClick }: ArrowBtnProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={direction === 'up' ? 'Upvote' : 'Downvote'}
      className={cn(
        'grid place-items-center rounded-full text-[var(--color-text-muted)] transition',
        btnSize,
        'hover:bg-[var(--color-bg-3)] hover:text-[var(--color-text)]',
        active && direction === 'up' && 'bg-[var(--color-accent-dim)] text-[var(--color-accent)] hover:bg-[var(--color-accent-dim)] hover:text-[var(--color-accent)]',
        active && direction === 'down' && 'bg-[rgba(255,106,138,0.12)] text-[var(--color-danger)] hover:bg-[rgba(255,106,138,0.12)] hover:text-[var(--color-danger)]',
      )}
    >
      {direction === 'up' ? <ArrowBigUp size={size} /> : <ArrowBigDown size={size} />}
    </button>
  );
}

function formatScore(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, '') + 'k';
  return String(n);
}

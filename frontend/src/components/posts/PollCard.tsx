import { useState, type MouseEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { votePoll } from '@/api/polls';
import type { Poll } from '@/features/posts/types';
import { useAppSelector } from '@/app/hooks';
import { timeAgo } from '@/lib/time';
import { cn } from '@/lib/cn';
import { Check } from 'lucide-react';

interface PollCardProps {
  poll: Poll;
  onUpdate?: (poll: Poll) => void;
}

export function PollCard({ poll, onUpdate }: PollCardProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const isAuthed = useAppSelector((s) => s.auth.status === 'authenticated');
  const [local, setLocal] = useState<Poll>(poll);
  const [busy, setBusy] = useState(false);

  const leadingPct = Math.max(0, ...local.options.map((o) => o.percent));
  const canVote = isAuthed && !local.is_closed && local.user_option === null;

  async function handleVote(optionId: number, e: MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (busy || !canVote) {
      if (!isAuthed) navigate('/login');
      return;
    }
    setBusy(true);
    try {
      const updated = await votePoll(local.id, optionId);
      setLocal(updated);
      onUpdate?.(updated);
    } catch {
      // ignore
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      {local.options.map((opt) => {
        const leading = opt.percent === leadingPct && local.total_votes > 0;
        const voted = local.user_option === opt.id;
        const revealed = local.user_option !== null || local.is_closed;
        return (
          <button
            key={opt.id}
            type="button"
            onClick={(e) => handleVote(opt.id, e)}
            disabled={!canVote || busy}
            className={cn(
              'relative flex items-center justify-between overflow-hidden rounded-[10px] border px-3.5 py-3 text-left text-[13.5px] transition',
              voted
                ? 'border-[var(--color-accent)] bg-[var(--color-bg-elevated)]'
                : 'border-[var(--color-border)] bg-[var(--color-bg-elevated)]',
              canVote && 'hover:border-[var(--color-accent)] cursor-pointer',
              !canVote && 'cursor-default',
            )}
          >
            {revealed && (
              <div
                className={cn(
                  'absolute inset-y-0 left-0 z-0 border-r transition-all',
                  voted
                    ? 'border-[var(--color-accent)]/50 bg-[var(--color-accent)]/20'
                    : leading
                      ? 'border-[var(--color-accent)]/40 bg-[var(--color-accent-dim)]'
                      : 'border-[var(--color-accent-border)] bg-[var(--color-accent)]/8',
                )}
                style={{ width: `${opt.percent}%` }}
              />
            )}
            <span className="relative z-10 flex items-center gap-2">
              {voted && (
                <Check strokeWidth={2.4} className="h-3.5 w-3.5 text-[var(--color-accent)]" />
              )}
              <span>{opt.text}</span>
            </span>
            {revealed && (
              <span
                className={cn(
                  'font-mono relative z-10 text-[12px]',
                  voted
                    ? 'text-[var(--color-accent)] font-semibold'
                    : leading
                      ? 'text-[var(--color-accent)]'
                      : 'text-[var(--color-text-muted)]',
                )}
              >
                {opt.percent.toFixed(0)}%
              </span>
            )}
          </button>
        );
      })}

      <div className="font-mono mt-1 flex items-center gap-2 text-[12px] text-[var(--color-text-dim)]">
        <span>{t('poll.votes', { count: local.total_votes })}</span>
        <span>·</span>
        <span>
          {local.is_closed ? t('poll.closed') : t('poll.closes', { time: timeAgo(local.closes_at) })}
        </span>
        {!isAuthed && !local.is_closed && (
          <>
            <span>·</span>
            <button
              type="button"
              onClick={(e) => {
                e.preventDefault();
                navigate('/login');
              }}
              className="text-[var(--color-accent)] hover:underline"
            >
              {t('poll.loginToVote')}
            </button>
          </>
        )}
      </div>
    </div>
  );
}

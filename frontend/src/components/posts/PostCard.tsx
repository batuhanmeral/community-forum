import { Link } from 'react-router-dom';
import type { Post } from '@/features/posts/types';
import { Badge } from '@/components/ui/Badge';
import { Card } from '@/components/ui/Card';
import { timeAgo } from '@/lib/time';
import { cn } from '@/lib/cn';

interface PostCardProps {
  post: Post;
  hideCommunity?: boolean;
}

export function PostCard({ post, hideCommunity }: PostCardProps) {
  return (
    <Card padded={false} interactive className="overflow-hidden">
      <div className="flex">
        <div className="flex w-12 shrink-0 flex-col items-center gap-1 bg-[var(--color-bg-elevated)] py-3 text-xs text-[var(--color-text-muted)]">
          <button
            type="button"
            aria-label="Upvote"
            className={cn(
              'rounded p-1 transition-colors hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-accent)]',
              post.user_vote === 1 && 'text-[var(--color-accent)]',
            )}
            onClick={(e) => e.preventDefault()}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
              <path d="M12 5v14M6 11l6-6 6 6" />
            </svg>
          </button>
          <span className="font-semibold text-[var(--color-text)]">
            {formatScore(post.score)}
          </span>
          <button
            type="button"
            aria-label="Downvote"
            className={cn(
              'rounded p-1 transition-colors hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-danger)]',
              post.user_vote === -1 && 'text-[var(--color-danger)]',
            )}
            onClick={(e) => e.preventDefault()}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
              <path d="M12 5v14M6 13l6 6 6-6" />
            </svg>
          </button>
        </div>

        <Link to={`/posts/${post.id}`} className="min-w-0 flex-1 p-3">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-[var(--color-text-muted)]">
            {!hideCommunity && (
              <Link
                to={`/c/${post.community}`}
                onClick={(e) => e.stopPropagation()}
                className="font-semibold text-[var(--color-text)] hover:underline"
              >
                c/{post.community}
              </Link>
            )}
            <span className="text-[var(--color-text-dim)]">·</span>
            <span>{timeAgo(post.created_at)}</span>
            {post.edited_at && (
              <span className="text-[var(--color-text-dim)] italic">(edited)</span>
            )}
            {post.is_pinned && <Badge tone="accent">Pinned</Badge>}
            {post.is_nsfw && <Badge tone="danger">NSFW</Badge>}
          </div>
          <h3 className="mt-1 line-clamp-2 text-base font-semibold text-[var(--color-text)]">
            {post.title}
          </h3>

          {post.kind === 'link' && post.url && (
            <a
              href={post.url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="mt-1 inline-flex items-center gap-1 text-xs text-[var(--color-accent)] hover:underline"
            >
              {tryHostname(post.url)}
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3 w-3">
                <path d="M7 17 17 7M9 7h8v8" />
              </svg>
            </a>
          )}

          {post.kind === 'image' && post.image && (
            <div className="mt-2 overflow-hidden rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-elevated)]">
              <img
                src={post.image}
                alt={post.title}
                className={cn('max-h-96 w-full object-contain', post.is_nsfw && 'blur-2xl hover:blur-0 transition')}
                loading="lazy"
              />
            </div>
          )}

          {post.kind === 'text' && post.body && (
            <p className="mt-1 line-clamp-3 text-sm text-[var(--color-text-muted)] whitespace-pre-wrap">
              {post.body}
            </p>
          )}

          {post.kind === 'poll' && post.poll && (
            <p className="mt-1 text-xs text-[var(--color-text-muted)]">
              Poll · {post.poll.total_votes} vote{post.poll.total_votes === 1 ? '' : 's'}
            </p>
          )}
        </Link>
      </div>
    </Card>
  );
}

function formatScore(score: number): string {
  const abs = Math.abs(score);
  if (abs >= 1000) return (score / 1000).toFixed(1).replace(/\.0$/, '') + 'k';
  return String(score);
}

function tryHostname(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

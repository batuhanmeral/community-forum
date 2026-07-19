import { Link } from 'react-router-dom';
import type { Post } from '@/features/posts/types';
import type { VoteValue } from '@/api/votes';
import { VoteCluster } from '@/components/votes/VoteCluster';
import { SaveButton } from '@/components/saves/SaveButton';
import { timeAgo } from '@/lib/time';
import { cn } from '@/lib/cn';

interface PostCardProps {
  post: Post;
  hideCommunity?: boolean;
}

export function PostCard({ post, hideCommunity }: PostCardProps) {
  const isPinned = post.is_pinned;

  return (
    <article
      className={cn(
        'relative mb-3.5 rounded-[14px] border border-[var(--color-border)] bg-[var(--color-bg-1)] px-[22px] pb-3.5 pt-5 transition hover:border-[var(--color-border-strong)]',
        isPinned && 'border-[rgba(97,218,251,0.18)]',
      )}
    >
      {isPinned && (
        <span
          className="absolute left-[22px] right-[22px] top-0 h-px opacity-50"
          style={{ background: 'linear-gradient(90deg, transparent, var(--color-accent), transparent)' }}
        />
      )}

      <Link to={`/posts/${post.id}`} className="block">
        {/* Meta row */}
        <div className="mb-3 flex items-center gap-2 text-[13px] text-[var(--color-text-muted)]">
          {!hideCommunity && (
            <Link
              to={`/c/${post.community}`}
              onClick={(e) => e.stopPropagation()}
              className="inline-flex items-center gap-1.5 font-medium text-[var(--color-text)] hover:text-[var(--color-accent)]"
            >
              <span
                className="grid h-[22px] w-[22px] place-items-center rounded-full border text-[11px] font-bold text-[var(--color-accent)]"
                style={{
                  background: 'linear-gradient(135deg, #1d2a35, #0d1418)',
                  borderColor: 'rgba(97, 218, 251, 0.2)',
                }}
              >
                {post.community[0]?.toUpperCase()}
              </span>
              <span>c/{post.community}</span>
            </Link>
          )}
          <span className="text-[var(--color-text-dim)]">·</span>
          <span className="text-[var(--color-text-soft)]">
            {post.author ? `u/anon-${post.author}` : 'u/deleted'}
          </span>
          <span className="text-[var(--color-text-dim)]">·</span>
          <span className="font-mono text-[12px] text-[var(--color-text-dim)]">{timeAgo(post.created_at)}</span>
          {post.kind === 'poll' && <Flair kind="discussion">Poll</Flair>}
          {post.kind === 'image' && <Flair kind="showcase">Image</Flair>}
          {post.kind === 'link' && <Flair kind="news">Link</Flair>}
          {post.is_nsfw && <Flair kind="news">NSFW</Flair>}
          {isPinned && (
            <span className="ml-auto inline-flex items-center gap-1.5 text-[11px] font-medium text-[var(--color-accent)]">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-3 w-3">
                <path d="M12 17v5m4-12V4H8v6L5 13v2h14v-2z" />
              </svg>
              Pinned by mods
            </span>
          )}
        </div>

        {/* Title */}
        <h2 className="mb-2.5 text-[19px] font-semibold leading-[1.3] tracking-tight text-[var(--color-text)]">
          {post.title}
        </h2>

        {/* Body / content */}
        {post.kind === 'text' && post.body && (
          <p className="mb-3.5 line-clamp-3 max-w-[68ch] text-[14.5px] leading-relaxed text-[var(--color-text-soft)] whitespace-pre-wrap">
            {post.body}
          </p>
        )}

        {post.kind === 'link' && post.url && (
          <a
            href={post.url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="mb-3.5 flex gap-3.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-3.5 transition hover:border-[var(--color-border-strong)] hover:bg-[var(--color-bg-3)]"
          >
            <div
              className="h-[84px] w-[110px] shrink-0 rounded-lg border border-[var(--color-border)]"
              style={{
                background: `repeating-linear-gradient(135deg, rgba(255,255,255,0.025) 0 8px, transparent 8px 16px),
                             linear-gradient(135deg, #1a2530, #0e1518)`,
              }}
            />
            <div className="min-w-0 flex-1">
              <div className="font-mono mb-1.5 flex items-center gap-2 text-[11.5px] text-[var(--color-text-dim)]">
                <span
                  className="block h-[14px] w-[14px] rounded-sm"
                  style={{ background: 'linear-gradient(135deg, var(--color-accent), #2faed0)' }}
                />
                <span>{tryHostname(post.url)}</span>
                <span>·</span>
                <span>External link</span>
              </div>
              <div className="mb-1 line-clamp-1 text-[14.5px] font-medium leading-snug text-[var(--color-text)]">
                {post.title}
              </div>
              <div className="line-clamp-2 text-[12.5px] leading-snug text-[var(--color-text-muted)]">
                {post.body || post.url}
              </div>
            </div>
          </a>
        )}

        {post.kind === 'image' && post.image && (
          <div
            className="-mx-[22px] mb-3.5 grid h-[360px] place-items-center overflow-hidden border-y border-[var(--color-border)] bg-[var(--color-bg-elevated)]"
            style={{
              background: `repeating-linear-gradient(135deg, rgba(255,255,255,0.018) 0 12px, transparent 12px 24px), var(--color-bg-elevated)`,
            }}
          >
            <img
              src={post.image}
              alt={post.title}
              className={cn('max-h-full max-w-full object-contain', post.is_nsfw && 'blur-2xl transition hover:blur-0')}
              loading="lazy"
            />
          </div>
        )}

        {post.kind === 'poll' && post.poll && (
          <div className="mb-3.5 flex flex-col gap-2">
            {post.poll.options.map((opt) => {
              const leading = opt.percent === Math.max(...post.poll!.options.map((o) => o.percent));
              return (
                <div
                  key={opt.id}
                  className="relative flex items-center justify-between overflow-hidden rounded-[10px] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3.5 py-3 text-[13.5px]"
                >
                  <div
                    className="absolute inset-y-0 left-0 z-0"
                    style={{
                      width: `${opt.percent}%`,
                      background: leading ? 'rgba(97, 218, 251, 0.14)' : 'rgba(97, 218, 251, 0.08)',
                      borderRight: `1px solid ${leading ? 'rgba(97, 218, 251, 0.4)' : 'rgba(97, 218, 251, 0.18)'}`,
                    }}
                  />
                  <span className="relative z-10">{opt.text}</span>
                  <span className={cn('font-mono relative z-10 text-[12px]', leading ? 'text-[var(--color-accent)]' : 'text-[var(--color-text-muted)]')}>
                    {opt.percent.toFixed(0)}%
                  </span>
                </div>
              );
            })}
            <div className="font-mono text-[12px] text-[var(--color-text-dim)]">
              {post.poll.total_votes} votes · {post.poll.is_closed ? 'closed' : `closes ${timeAgo(post.poll.closes_at)}`}
            </div>
          </div>
        )}
      </Link>

      {/* Actions bar */}
      <div className="flex items-center gap-1.5 pt-1.5">
        <VoteCluster
          target="post"
          objectId={post.id}
          score={post.score}
          userVote={post.user_vote as VoteValue | null}
        />

        <ActionBtn href={`/posts/${post.id}`} icon={
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className="h-[15px] w-[15px]">
            <path d="M21 11.5a8.4 8.4 0 0 1-8.5 8.5 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.4 8.4 0 0 1 8.5-8.5 8.4 8.4 0 0 1 8.5 8.5z" />
          </svg>
        }>
          <span className="font-mono text-[12px] text-[var(--color-text-dim)]">0</span>
        </ActionBtn>

        <ActionBtn icon={
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className="h-[15px] w-[15px]">
            <path d="M4 12v8h16v-8M16 6l-4-4-4 4m4-4v14" />
          </svg>
        }>
          <span>Share</span>
        </ActionBtn>

        <SaveButton target="post" objectId={post.id} initialSaved={post.is_saved} />

        <div className="flex-1" />

        <ActionBtn icon={
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className="h-[15px] w-[15px]">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8S1 12 1 12z" />
            <circle cx="12" cy="12" r="3" />
          </svg>
        }>
          <span className="font-mono text-[12px] text-[var(--color-text-dim)]">{formatScore(Math.max(post.score, 1) * 12)}</span>
        </ActionBtn>
      </div>
    </article>
  );
}

function ActionBtn({ href, icon, children }: { href?: string; icon: React.ReactNode; children?: React.ReactNode }) {
  const cls = 'inline-flex items-center gap-[7px] rounded-full px-3 py-2 text-[13px] text-[var(--color-text-muted)] transition hover:bg-[var(--color-bg-elevated)] hover:text-[var(--color-text)]';
  if (href) {
    return (
      <Link to={href} className={cls}>
        {icon}
        {children}
      </Link>
    );
  }
  return (
    <button type="button" className={cls} onClick={(e) => e.preventDefault()}>
      {icon}
      {children}
    </button>
  );
}

function Flair({ kind, children }: { kind: 'discussion' | 'showcase' | 'question' | 'news'; children: React.ReactNode }) {
  const palette: Record<typeof kind, string> = {
    discussion: 'bg-[rgba(97,218,251,0.08)] text-[var(--color-accent)] border-[rgba(97,218,251,0.2)]',
    showcase: 'bg-[rgba(106,255,193,0.08)] text-[var(--color-success)] border-[rgba(106,255,193,0.2)]',
    question: 'bg-[rgba(255,155,106,0.08)] text-[var(--color-warn)] border-[rgba(255,155,106,0.2)]',
    news: 'bg-[rgba(255,106,138,0.08)] text-[var(--color-danger)] border-[rgba(255,106,138,0.2)]',
  };
  return (
    <span className={cn('inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium', palette[kind])}>
      {children}
    </span>
  );
}

function formatScore(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, '') + 'k';
  return String(n);
}

function tryHostname(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

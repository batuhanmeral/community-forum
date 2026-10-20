import { Link } from 'react-router-dom';
import type { Post } from '@/features/posts/types';
import type { VoteValue } from '@/api/votes';
import { NsfwReveal } from '@/components/posts/NsfwReveal';
import { VoteCluster } from '@/components/votes/VoteCluster';
import { SaveButton } from '@/components/saves/SaveButton';
import { userPath } from '@/lib/paths';
import { timeAgo } from '@/lib/time';
import { cn } from '@/lib/cn';
import { MessageSquare, Pin, Share } from 'lucide-react';

interface PostCardProps {
  post: Post;
  hideCommunity?: boolean;
}

export function PostCard({ post, hideCommunity }: PostCardProps) {
  const isPinned = post.is_pinned;
  const image = post.image && (
    <img src={post.image} alt={post.title} className="max-h-[420px] w-full object-contain" loading="lazy" />
  );

  return (
    <article
      className={cn(
        'group relative mb-2 rounded-2xl border border-transparent px-3 py-2.5 transition-colors duration-150 hover:border-[var(--color-border)] hover:bg-[var(--color-bg-1)]',
        isPinned && 'border-[rgba(97,218,251,0.16)] bg-[rgba(97,218,251,0.025)]',
      )}
    >
      <div>
        {/* Meta row */}
        <div className="mb-1.5 flex items-center gap-1.5 text-[12px] text-[var(--color-text-muted)]">
          {!hideCommunity && (
            <Link
              to={`/c/${post.community}`}
              className="relative z-10 inline-flex items-center gap-1.5 font-semibold text-[var(--color-text)] hover:text-[var(--color-accent)]"
            >
              <span
                className="grid h-5 w-5 place-items-center rounded-full text-[10px] font-bold text-[var(--color-accent)]"
                style={{
                  background: 'linear-gradient(135deg, #1d2a35, #0d1418)',
                  border: '1px solid rgba(97, 218, 251, 0.2)',
                }}
              >
                {post.community[0]?.toUpperCase()}
              </span>
              <span>c/{post.community}</span>
            </Link>
          )}
          {post.author_username ? (
            <Link
              to={userPath(post.author_username)}
              className="relative z-10 text-[var(--color-text-soft)] hover:text-[var(--color-accent)]"
            >
              u/{post.author_username}
            </Link>
          ) : (
            <span className="text-[var(--color-text-soft)]">u/[deleted]</span>
          )}
          <span className="text-[var(--color-text-dim)]">·</span>
          <span className="font-mono text-[11.5px] text-[var(--color-text-dim)]">{timeAgo(post.created_at)}</span>
          {post.flair_detail && (
            <span
              className="inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium"
              style={{
                color: post.flair_detail.color,
                borderColor: `${post.flair_detail.color}44`,
                background: `${post.flair_detail.color}14`,
              }}
            >
              {post.flair_detail.name}
            </span>
          )}
          {post.kind === 'poll' && <Flair kind="discussion">Poll</Flair>}
          {post.kind === 'image' && <Flair kind="showcase">Image</Flair>}
          {post.kind === 'link' && <Flair kind="news">Link</Flair>}
          {post.is_nsfw && <Flair kind="news">NSFW</Flair>}
          {isPinned && (
            <span className="ml-auto inline-flex items-center gap-1 text-[11px] font-medium text-[var(--color-accent)]">
              <Pin className="h-3 w-3" />
              Pinned
            </span>
          )}
        </div>

        {/* Title */}
        <h2 className="mb-1.5 text-[17px] font-semibold leading-snug tracking-tight text-[var(--color-text)]">
          {/* The ::after overlay makes the whole card clickable without nesting links */}
          <Link
            to={`/posts/${post.id}`}
            className="outline-none after:absolute after:inset-0 after:rounded-2xl focus-visible:after:ring-2 focus-visible:after:ring-[var(--color-accent)]"
          >
            {post.title}
          </Link>
        </h2>

        {/* Body / content */}
        {post.kind === 'text' && post.body && (
          <p className="mb-2 line-clamp-3 max-w-[70ch] text-[14px] leading-relaxed text-[var(--color-text-soft)] whitespace-pre-wrap">
            {post.body}
          </p>
        )}

        {post.kind === 'link' && post.url && (
          <a
            href={post.url}
            target="_blank"
            rel="noopener noreferrer"
            className="relative z-10 mb-2 flex gap-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-2.5 transition hover:border-[var(--color-border-strong)] hover:bg-[var(--color-bg-3)]"
          >
            <div
              className="h-[72px] w-[96px] shrink-0 rounded-lg border border-[var(--color-border)]"
              style={{
                background: `repeating-linear-gradient(135deg, rgba(255,255,255,0.025) 0 8px, transparent 8px 16px),
                             linear-gradient(135deg, #1a2530, #0e1518)`,
              }}
            />
            <div className="min-w-0 flex-1">
              <div className="font-mono mb-1.5 flex items-center gap-2 text-[11px] text-[var(--color-text-dim)]">
                <span
                  className="block h-[12px] w-[12px] rounded-sm"
                  style={{ background: 'linear-gradient(135deg, var(--color-accent), #2faed0)' }}
                />
                <span>{tryHostname(post.url)}</span>
                <span>·</span>
                <span>External link</span>
              </div>
              <div className="mb-1 line-clamp-1 text-[14px] font-medium leading-snug text-[var(--color-text)]">
                {post.title}
              </div>
              <div className="line-clamp-2 text-[12px] leading-snug text-[var(--color-text-muted)]">
                {post.body || post.url}
              </div>
            </div>
          </a>
        )}

        {post.kind === 'image' && post.image && (
          <div
            className="mb-2 grid max-h-[420px] place-items-center overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)]"
            style={{
              background: `repeating-linear-gradient(135deg, rgba(255,255,255,0.018) 0 12px, transparent 12px 24px), var(--color-bg-elevated)`,
            }}
          >
            {post.is_nsfw ? <NsfwReveal>{image}</NsfwReveal> : image}
          </div>
        )}

        {post.kind === 'poll' && post.poll && (
          <div className="mb-2 flex flex-col gap-2">
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
      </div>

      {/* Actions bar; z-10 keeps it above the title's stretched link */}
      <div className="relative z-10 mt-2 flex w-fit items-center gap-1.5">
        <VoteCluster
          target="post"
          objectId={post.id}
          score={post.score}
          userVote={post.user_vote as VoteValue | null}
          size="sm"
        />

        <ActionBtn href={`/posts/${post.id}`} icon={
          <MessageSquare className="h-[15px] w-[15px]" />
        }>
          <span className="font-mono text-[12px]">{post.comment_count}</span>
        </ActionBtn>

        <ActionBtn icon={
          <Share className="h-[15px] w-[15px]" />
        }>
          <span className="max-[480px]:hidden">Share</span>
        </ActionBtn>

        <SaveButton target="post" objectId={post.id} initialSaved={post.is_saved} />
      </div>
    </article>
  );
}

function ActionBtn({ href, icon, children }: { href?: string; icon: React.ReactNode; children?: React.ReactNode }) {
  const cls = 'inline-flex items-center gap-1.5 rounded-full bg-[var(--color-bg-elevated)] px-3 py-1.5 text-[12.5px] font-medium text-[var(--color-text-muted)] transition hover:bg-[var(--color-bg-3)] hover:text-[var(--color-text)]';
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

function tryHostname(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import type { Post } from '@/features/posts/types';
import type { VoteValue } from '@/api/votes';
import { NsfwReveal } from '@/components/posts/NsfwReveal';
import { VoteCluster } from '@/components/votes/VoteCluster';
import { SaveButton } from '@/components/saves/SaveButton';
import { ShareButton } from '@/components/posts/ShareButton';
import { userPath } from '@/lib/paths';
import { timeAgo } from '@/lib/time';
import { cn } from '@/lib/cn';
import { deletedBodyKey } from '@/lib/deletedBody';
import { MessageSquare, Pin } from 'lucide-react';

interface PostCardProps {
  post: Post;
  hideCommunity?: boolean;
}

export function PostCard({ post, hideCommunity }: PostCardProps) {
  // Subscribes to language changes so timeAgo() re-renders in the new language.
  const { t } = useTranslation();
  const isPinned = post.is_pinned;
  // Saved deleted posts still reach the card; the API's English body marker is swapped for the reader's language.
  const body = post.is_deleted ? t(deletedBodyKey(post.body)) : post.body;
  const image = post.image && (
    <img src={post.image} alt={post.title} className="max-h-[420px] w-full object-contain" loading="lazy" />
  );

  return (
    <article
      className={cn(
        'group relative mb-3 rounded-[var(--radius-card)] border bg-[var(--color-bg-1)] px-4 py-3 transition-colors duration-150 hover:border-[var(--color-link)]',
        isPinned ? 'border-[var(--color-link-border)]' : 'border-[var(--color-border-strong)]',
      )}
    >
      <div>
        {/* Meta row */}
        <div className="mb-1.5 flex flex-wrap items-center gap-x-1.5 gap-y-1 text-[12px] text-[var(--color-text-muted)]">
          {!hideCommunity && (
            <Link
              to={`/c/${post.community}`}
              className="relative z-10 inline-flex items-center gap-1.5 font-semibold text-[var(--color-text)] hover:text-[var(--color-link)]"
            >
              <span
                className="grid h-5 w-5 place-items-center rounded-[var(--radius-avatar)] border border-[var(--color-link-border)] bg-[var(--color-bg-3)] text-[10px] font-bold text-[var(--color-link)]"
              >
                {post.community[0]?.toUpperCase()}
              </span>
              <span>c/{post.community}</span>
            </Link>
          )}
          {post.author_username ? (
            <Link
              to={userPath(post.author_username)}
              className="relative z-10 text-[var(--color-text-soft)] hover:text-[var(--color-link)]"
            >
              u/{post.author_username}
            </Link>
          ) : (
            <span className="text-[var(--color-text-soft)]">u/{t('common.deleted')}</span>
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
          {post.kind === 'poll' && <Flair kind="discussion">{t('post.kind_poll')}</Flair>}
          {post.kind === 'image' && <Flair kind="showcase">{t('post.kind_image')}</Flair>}
          {post.kind === 'link' && <Flair kind="news">{t('post.kind_link')}</Flair>}
          {post.is_nsfw && <Flair kind="news">{t('post.nsfw')}</Flair>}
          {isPinned && (
            <span className="ml-auto inline-flex items-center gap-1 text-[11px] font-medium text-[var(--color-link)]">
              <Pin className="h-3 w-3" />
              {t('post.pinned')}
            </span>
          )}
        </div>

        {/* Title */}
        <h2 className="mb-1.5 text-[17px] font-semibold leading-snug tracking-tight text-[var(--color-text)]">
          {/* The ::after overlay makes the whole card clickable without nesting links */}
          <Link
            to={`/posts/${post.id}`}
            className="outline-none after:absolute after:inset-0 after:rounded-[var(--radius-card)] focus-visible:after:ring-2 focus-visible:after:ring-[var(--color-link)]"
          >
            {post.title}
          </Link>
        </h2>

        {/* Body / content */}
        {post.kind === 'text' && body && (
          <p className="mb-2 line-clamp-3 max-w-[70ch] text-[14px] leading-relaxed text-[var(--color-text-soft)] whitespace-pre-wrap">
            {body}
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
              className="h-[72px] w-[96px] shrink-0 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-3)]"
            />
            <div className="min-w-0 flex-1">
              <div className="font-mono mb-1.5 flex items-center gap-2 text-[11px] text-[var(--color-text-dim)]">
                <span
                  className="block h-[12px] w-[12px] rounded-sm bg-[var(--color-link)]"
                />
                <span>{tryHostname(post.url)}</span>
                <span>·</span>
                <span>{t('post.externalLink')}</span>
              </div>
              <div className="mb-1 line-clamp-1 text-[14px] font-medium leading-snug text-[var(--color-text)]">
                {post.title}
              </div>
              <div className="line-clamp-2 text-[12px] leading-snug text-[var(--color-text-muted)]">
                {body || post.url}
              </div>
            </div>
          </a>
        )}

        {post.kind === 'image' && post.image && (
          <div
            className="mb-2 grid max-h-[420px] place-items-center overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)]"
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
                    className={cn(
                      'absolute inset-y-0 left-0 z-0 border-r',
                      leading
                        ? 'border-[var(--color-link)]/40 bg-[var(--color-link-dim)]'
                        : 'border-[var(--color-link-border)] bg-[var(--color-link)]/8',
                    )}
                    style={{ width: `${opt.percent}%` }}
                  />
                  <span className="relative z-10">{opt.text}</span>
                  <span className={cn('font-mono relative z-10 text-[12px]', leading ? 'text-[var(--color-link)]' : 'text-[var(--color-text-muted)]')}>
                    {opt.percent.toFixed(0)}%
                  </span>
                </div>
              );
            })}
            <div className="font-mono text-[12px] text-[var(--color-text-dim)]">
              {t('poll.votes', { count: post.poll.total_votes })} · {post.poll.is_closed ? t('poll.closedInline') : t('poll.closes', { time: timeAgo(post.poll.closes_at) })}
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

        <ShareButton postId={post.id} title={post.title} />

        <SaveButton target="post" objectId={post.id} initialSaved={post.is_saved} />
      </div>
    </article>
  );
}

const ACTION_BTN_CLASSES = 'inline-flex items-center gap-1.5 rounded-[var(--radius-control)] bg-[var(--color-bg-elevated)] px-3 py-1.5 text-[12.5px] font-medium text-[var(--color-text-muted)] transition hover:bg-[var(--color-bg-3)] hover:text-[var(--color-text)]';

function ActionBtn({ href, icon, children }: { href: string; icon: React.ReactNode; children?: React.ReactNode }) {
  return (
    <Link to={href} className={ACTION_BTN_CLASSES}>
      {icon}
      {children}
    </Link>
  );
}

function Flair({ kind, children }: { kind: 'discussion' | 'showcase' | 'question' | 'news'; children: React.ReactNode }) {
  const palette: Record<typeof kind, string> = {
    discussion: 'bg-[var(--color-link)]/8 text-[var(--color-link)] border-[var(--color-link-border)]',
    showcase: 'bg-[var(--color-success-dim)] text-[var(--color-success)] border-[var(--color-success)]/20',
    question: 'bg-[var(--color-warn-dim)] text-[var(--color-warn)] border-[var(--color-warn)]/20',
    news: 'bg-[var(--color-danger-dim)] text-[var(--color-danger)] border-[var(--color-danger)]/20',
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

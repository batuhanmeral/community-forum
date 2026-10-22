import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { listSaved, type SavedItem } from '@/api/saves';
import type { Post } from '@/features/posts/types';
import type { Comment } from '@/features/comments/types';
import { Card } from '@/components/ui/Card';
import { PageTitle } from '@/components/ui/PageTitle';
import { PostCard } from '@/components/posts/PostCard';
import { timeAgo } from '@/lib/time';
import { cn } from '@/lib/cn';
import { deletedBodyKey } from '@/lib/deletedBody';
import { ArrowRight } from 'lucide-react';

type Filter = 'all' | 'post' | 'comment';

export function SavedPage() {
  const { t } = useTranslation();
  const [items, setItems] = useState<SavedItem[]>([]);
  const [filter, setFilter] = useState<Filter>('all');
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setPage(1);
    listSaved(filter === 'all' ? undefined : filter, 1)
      .then((d) => {
        if (cancelled) return;
        setItems(d.results);
        setHasMore(Boolean(d.next));
      })
      .catch(() => undefined)
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [filter]);

  async function loadMore() {
    if (loadingMore || !hasMore) return;
    const next = page + 1;
    setLoadingMore(true);
    try {
      const d = await listSaved(filter === 'all' ? undefined : filter, next);
      setItems((arr) => [...arr, ...d.results]);
      setHasMore(Boolean(d.next));
      setPage(next);
    } finally {
      setLoadingMore(false);
    }
  }

  const counts = useMemo(() => {
    return {
      all: items.length,
      post: items.filter((i) => i.target_type === 'post').length,
      comment: items.filter((i) => i.target_type === 'comment').length,
    };
  }, [items]);

  return (
    <div className="flex flex-col gap-4">
      <PageTitle title={t('titles.saved')} />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight">{t('titles.saved')}</h1>
          <p className="font-mono text-[12px] text-[var(--color-text-dim)]">
            {t('savedPage.subtitle')}
          </p>
        </div>
        <div className="flex gap-0.5 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-1)] p-1">
          {(['all', 'post', 'comment'] as Filter[]).map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              className={cn(
                'inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-[13px] font-medium transition',
                filter === f
                  ? 'bg-[var(--color-bg-3)] text-[var(--color-text)]'
                  : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]',
              )}
            >
              {t(`savedPage.filter_${f}`)}
              <span className="font-mono text-[11px] opacity-70">{counts[f]}</span>
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <Card>
          <p className="text-sm text-[var(--color-text-muted)]">{t('common.loading')}</p>
        </Card>
      ) : items.length === 0 ? (
        <Card>
          <p className="text-sm text-[var(--color-text-muted)]">
            {t('savedPage.empty')}{' '}
            <Link to="/" className="inline-flex items-center gap-1 text-[var(--color-link)] underline underline-offset-2 hover:text-[var(--color-link-hover)]">
              {t('savedPage.browseFeed')}
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </p>
        </Card>
      ) : (
        <div className="flex flex-col gap-3">
          {items.map((item) =>
            item.target_type === 'post' && item.target ? (
              <PostCard key={item.id} post={item.target as Post} />
            ) : item.target_type === 'comment' && item.target ? (
              <SavedCommentRow key={item.id} comment={item.target as Comment} />
            ) : null,
          )}
        </div>
      )}

      {hasMore && (
        <div className="py-2 text-center">
          <button
            type="button"
            onClick={loadMore}
            disabled={loadingMore}
            className="inline-flex items-center gap-1.5 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-4 py-2 text-[13px] font-medium text-[var(--color-text-soft)] transition hover:bg-[var(--color-bg-3)] hover:text-[var(--color-text)] disabled:opacity-60"
          >
            {loadingMore ? t('common.loading') : t('common.loadMore')}
          </button>
        </div>
      )}
    </div>
  );
}

function SavedCommentRow({ comment }: { comment: Comment }) {
  // Subscribes to language changes so timeAgo() re-renders in the new language.
  const { t } = useTranslation();
  return (
    <Link
      to={`/posts/${comment.post}`}
      className="block rounded-[14px] border border-[var(--color-border)] bg-[var(--color-bg-1)] px-4 py-3 transition hover:border-[var(--color-border-strong)]"
    >
      <div className="font-mono mb-1 flex items-center gap-2 text-[11.5px] text-[var(--color-text-dim)]">
        <span>{t('savedPage.comment')}</span>
        <span>·</span>
        {comment.author_username ? (
          <span className="text-[var(--color-text-soft)]">u/{comment.author_username}</span>
        ) : (
          <span className="italic">{t('common.deleted')}</span>
        )}
        <span>·</span>
        <span>{timeAgo(comment.created_at)}</span>
      </div>
      <p className="line-clamp-3 text-sm text-[var(--color-text-soft)] whitespace-pre-wrap">
        {comment.is_deleted ? t(deletedBodyKey(comment.body)) : comment.body}
      </p>
    </Link>
  );
}

import { useCallback, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { approvePost, listApprovalQueue, rejectPost } from '@/api/posts';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { usePagedList } from '@/lib/usePagedList';
import { timeAgo } from '@/lib/time';

export function ApprovalQueueCard({ slug }: { slug: string }) {
  const { t } = useTranslation();
  const fetchPage = useCallback((page: number) => listApprovalQueue(slug, page), [slug]);
  const { items, loading, nextPage, loadMore, loadMoreFailed, remove } = usePagedList(fetchPage);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function act(id: number, kind: 'approve' | 'reject') {
    setBusyId(id);
    setError(null);
    try {
      if (kind === 'approve') await approvePost(id);
      else await rejectPost(id);
      remove(id);
    } catch {
      setError(t('mod.actionFailed'));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Card>
      <h2 className="text-base font-semibold tracking-tight">{t('mod.approvalTitle')}</h2>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">{t('mod.approvalHint')}</p>
      {error && <p className="mt-2 text-sm text-[var(--color-danger)]">{error}</p>}
      <div className="mt-3 flex flex-col gap-2">
        {loading ? (
          <p className="text-sm text-[var(--color-text-muted)]">{t('mod.loading')}</p>
        ) : items.length === 0 ? (
          <p className="text-sm text-[var(--color-text-muted)]">{t('mod.approvalEmpty')}</p>
        ) : (
          items.map((post) => (
            <div
              key={post.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-[12px] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-4 py-3"
            >
              <div className="min-w-0 flex-1">
                <Link
                  to={`/posts/${post.id}`}
                  className="text-sm font-medium text-[var(--color-text)] hover:underline"
                >
                  {post.title}
                </Link>
                <div className="mt-0.5 text-xs text-[var(--color-text-muted)]">
                  u/{post.author_username ?? '[deleted]'} · {timeAgo(post.created_at)}
                </div>
              </div>
              <div className="flex shrink-0 gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  loading={busyId === post.id}
                  onClick={() => act(post.id, 'reject')}
                >
                  {t('mod.reject')}
                </Button>
                <Button size="sm" loading={busyId === post.id} onClick={() => act(post.id, 'approve')}>
                  {t('mod.approve')}
                </Button>
              </div>
            </div>
          ))
        )}
      </div>
      {nextPage !== null && (
        <button
          type="button"
          onClick={loadMore}
          className="mt-3 text-sm text-[var(--color-accent)] hover:underline"
        >
          {t('mod.loadMore')}
        </button>
      )}
      {loadMoreFailed && (
        <p className="mt-2 text-sm text-[var(--color-danger)]">{t('mod.loadMoreFailed')}</p>
      )}
    </Card>
  );
}

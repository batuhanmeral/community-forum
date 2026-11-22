import { useCallback, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { listModmailInbox, listMyModmail, type ModmailStatus } from '@/api/modmail';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { PageTitle } from '@/components/ui/PageTitle';
import { timeAgo } from '@/lib/time';
import { usePagedList } from '@/lib/usePagedList';
import { cn } from '@/lib/cn';

/** `/c/:slug/modmail` is the moderators' shared inbox; `/modmail` lists the user's own threads. */
export function ModmailListPage({ inbox = false }: { inbox?: boolean }) {
  const { t } = useTranslation();
  const { slug = '' } = useParams<{ slug: string }>();
  const [status, setStatus] = useState<ModmailStatus>('open');
  const fetchPage = useCallback(
    (page: number) => (inbox ? listModmailInbox(slug, status, page) : listMyModmail(page)),
    [inbox, slug, status],
  );
  const { items, loading, loadFailed, nextPage, loadMore } = usePagedList(fetchPage);

  return (
    <div className="flex flex-col gap-4">
      <PageTitle title={t('modmail.title')} />
      <h1 className="text-[22px] font-semibold tracking-tight">
        {inbox ? t('modmail.inboxTitle', { slug }) : t('modmail.mineTitle')}
      </h1>
      {inbox && (
        <div role="tablist" className="flex gap-2">
          {(['open', 'archived'] as const).map((s) => (
            <button
              key={s}
              role="tab"
              type="button"
              aria-selected={status === s}
              onClick={() => setStatus(s)}
              className={cn(
                'rounded-full border px-3 py-1 text-sm',
                status === s
                  ? 'border-[var(--color-link)] text-[var(--color-link)]'
                  : 'border-[var(--color-border)] text-[var(--color-text-muted)]',
              )}
            >
              {t(`modmail.status_${s}`)}
            </button>
          ))}
        </div>
      )}
      {loading ? (
        <p className="text-sm text-[var(--color-text-muted)]">{t('common.loading')}</p>
      ) : loadFailed ? (
        <p role="alert" className="text-sm text-[var(--color-danger)]">
          {t('modmail.loadFailed')}
        </p>
      ) : items.length === 0 ? (
        <p className="text-sm text-[var(--color-text-muted)]">{t('modmail.empty')}</p>
      ) : (
        <Card padded={false}>
          {items.map((th, i) => (
            <Link
              key={th.id}
              to={`/modmail/${th.id}`}
              className={cn(
                'flex items-start justify-between gap-3 px-4 py-3 hover:bg-[var(--color-surface-hover)]',
                i > 0 && 'border-t border-[var(--color-border)]',
              )}
            >
              <div className="min-w-0">
                <p className={cn('truncate text-sm', th.unread ? 'font-semibold' : 'font-medium')}>
                  {th.subject}
                </p>
                <p className="mt-0.5 text-xs text-[var(--color-text-muted)]">
                  {inbox ? `u/${th.creator_username ?? t('common.deleted')}` : `c/${th.community}`}
                  {inbox && th.assigned_to_username ? ` · ${t('modmail.assignedTo', { name: th.assigned_to_username })}` : ''}
                  {' · '}
                  {timeAgo(th.updated)}
                </p>
              </div>
              {th.unread && (
                <span
                  role="img"
                  aria-label={t('modmail.unread')}
                  className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-[var(--color-link)]"
                />
              )}
            </Link>
          ))}
        </Card>
      )}
      {nextPage !== null && (
        <Button variant="secondary" onClick={() => void loadMore()}>
          {t('mod.loadMore')}
        </Button>
      )}
    </div>
  );
}

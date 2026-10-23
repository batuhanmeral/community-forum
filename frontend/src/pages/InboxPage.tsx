import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { listNotifications, markAllNotificationsRead, markNotificationRead } from '@/api/notifications';
import type { Notification } from '@/features/notifications/types';
import { formatNotification } from '@/features/notifications/format';
import { useAppDispatch, useAppSelector } from '@/app/hooks';
import { setUnreadCount } from '@/features/notifications/notificationSlice';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { PageTitle } from '@/components/ui/PageTitle';
import { timeAgo } from '@/lib/time';
import { cn } from '@/lib/cn';
import { NotificationIcon } from '@/components/notifications/NotificationIcon';
import { ArrowRight } from 'lucide-react';

type Filter = 'all' | 'unread';

export function InboxPage() {
  const { t } = useTranslation();
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const unreadCount = useAppSelector((s) => s.notifications.unreadCount);
  const [items, setItems] = useState<Notification[]>([]);
  const [filter, setFilter] = useState<Filter>('all');
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setPage(1);
    listNotifications({ unread: filter === 'unread', page: 1 })
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
      const d = await listNotifications({ unread: filter === 'unread', page: next });
      setItems((arr) => [...arr, ...d.results]);
      setHasMore(Boolean(d.next));
      setPage(next);
    } finally {
      setLoadingMore(false);
    }
  }

  async function handleMarkAll() {
    try {
      await markAllNotificationsRead();
      const now = new Date().toISOString();
      setItems((arr) => arr.map((n) => (n.read_at ? n : { ...n, read_at: now })));
      dispatch(setUnreadCount(0));
    } catch {
      // ignore
    }
  }

  async function handleClick(n: Notification) {
    const fmt = formatNotification(n, t);
    if (n.read_at === null) {
      try {
        await markNotificationRead(n.id);
        setItems((arr) => arr.map((x) => (x.id === n.id ? { ...x, read_at: new Date().toISOString() } : x)));
        dispatch(setUnreadCount(Math.max(0, unreadCount - 1)));
      } catch {
        // ignore
      }
    }
    if (fmt.to) navigate(fmt.to);
  }

  return (
    <div className="flex flex-col gap-4">
      <PageTitle title={t('titles.inbox')} />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight">{t('titles.inbox')}</h1>
          <p className="font-mono text-[12px] text-[var(--color-text-dim)]">
            {t('inbox.unread', { count: unreadCount })}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex gap-0.5 rounded-[var(--radius-control)] border border-[var(--color-border)] bg-[var(--color-bg-1)] p-1">
            {(['all', 'unread'] as Filter[]).map((f) => (
              <button
                key={f}
                type="button"
                onClick={() => setFilter(f)}
                className={cn(
                  'rounded-[var(--radius-control-inner)] px-3.5 py-1.5 text-[13px] font-medium transition',
                  filter === f
                    ? 'bg-[var(--color-bg-3)] text-[var(--color-text)]'
                    : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]',
                )}
              >
                {t(`inbox.filter_${f}`)}
              </button>
            ))}
          </div>
          {unreadCount > 0 && (
            <Button variant="secondary" size="sm" onClick={handleMarkAll}>
              {t('notifications.markAllRead')}
            </Button>
          )}
        </div>
      </div>

      {loading ? (
        <Card>
          <p className="text-sm text-[var(--color-text-muted)]">{t('common.loading')}</p>
        </Card>
      ) : items.length === 0 ? (
        <Card>
          <p className="text-sm text-[var(--color-text-muted)]">
            {filter === 'unread' ? t('inbox.caughtUp') : t('notifications.empty')}{' '}
            <Link to="/" className="inline-flex items-center gap-1 text-[var(--color-link)] underline underline-offset-2 hover:text-[var(--color-link-hover)]">
              {t('inbox.backToFeed')}
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </p>
        </Card>
      ) : (
        <Card padded={false}>
          {items.map((n, i) => {
            const fmt = formatNotification(n, t);
            const unread = n.read_at === null;
            return (
              <button
                key={n.id}
                type="button"
                onClick={() => handleClick(n)}
                className={cn(
                  'flex w-full items-start gap-3 px-4 py-3.5 text-left transition',
                  i > 0 && 'border-t border-[var(--color-border)]',
                  unread ? 'bg-[var(--color-link-dim)]/30 hover:bg-[var(--color-link-dim)]/50' : 'hover:bg-[var(--color-surface)]',
                )}
              >
                <span
                  className={cn(
                    'grid h-8 w-8 shrink-0 place-items-center rounded-[var(--radius-avatar)] text-[15px]',
                    unread
                      ? 'bg-[var(--color-link)] text-[var(--color-on-link)]'
                      : 'bg-[var(--color-bg-3)] text-[var(--color-text-muted)]',
                  )}
                >
                  <NotificationIcon kind={fmt.kind} />
                </span>
                <div className="min-w-0 flex-1">
                  <p className={cn('text-sm leading-snug', unread ? 'text-[var(--color-text)]' : 'text-[var(--color-text-soft)]')}>
                    {fmt.text}
                  </p>
                  <p className="font-mono mt-0.5 text-[11px] text-[var(--color-text-dim)]">
                    {timeAgo(n.created_at)}
                  </p>
                </div>
                {unread && <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-[var(--color-link)]" />}
              </button>
            );
          })}
        </Card>
      )}

      {hasMore && (
        <div className="py-2 text-center">
          <button
            type="button"
            onClick={loadMore}
            disabled={loadingMore}
            className="inline-flex items-center gap-1.5 rounded-[var(--radius-control)] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-4 py-2 text-[13px] font-medium text-[var(--color-text-soft)] transition hover:bg-[var(--color-bg-3)] hover:text-[var(--color-text)] disabled:opacity-60"
          >
            {loadingMore ? t('common.loading') : t('common.loadMore')}
          </button>
        </div>
      )}
    </div>
  );
}

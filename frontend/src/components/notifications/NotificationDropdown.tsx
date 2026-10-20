import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { listNotifications, markAllNotificationsRead, markNotificationRead } from '@/api/notifications';
import type { Notification } from '@/features/notifications/types';
import { formatNotification } from '@/features/notifications/format';
import { useAppDispatch } from '@/app/hooks';
import { setUnreadCount } from '@/features/notifications/notificationSlice';
import { timeAgo } from '@/lib/time';
import { cn } from '@/lib/cn';
import { NotificationIcon } from '@/components/notifications/NotificationIcon';
import { ArrowRight, Bell } from 'lucide-react';

interface NotificationDropdownProps {
  unreadCount: number;
}

export function NotificationDropdown({ unreadCount }: NotificationDropdownProps) {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    listNotifications({ page: 1 })
      .then((d) => setItems(d.results.slice(0, 10)))
      .catch(() => undefined)
      .finally(() => setLoading(false));
  }, [open]);

  async function handleClickItem(n: Notification) {
    const fmt = formatNotification(n);
    if (n.read_at === null) {
      try {
        await markNotificationRead(n.id);
        setItems((arr) => arr.map((x) => (x.id === n.id ? { ...x, read_at: new Date().toISOString() } : x)));
        dispatch(setUnreadCount(Math.max(0, unreadCount - 1)));
      } catch {
        // ignore
      }
    }
    setOpen(false);
    if (fmt.to) navigate(fmt.to);
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

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        title="Notifications"
        aria-label="Notifications"
        className={cn(
          'relative grid h-[38px] w-[38px] place-items-center rounded-[11px]',
          'text-[var(--color-text-soft)] transition hover:bg-[var(--color-bg-elevated)] hover:text-[var(--color-text)]',
          open && 'bg-[var(--color-bg-elevated)] text-[var(--color-text)]',
        )}
      >
        <Bell className="h-[18px] w-[18px]" />
        {unreadCount > 0 && (
          <span
            className="font-mono absolute -right-1 -top-1 inline-flex h-4 min-w-[16px] items-center justify-center rounded-full bg-[var(--color-accent)] px-1 text-[10px] font-bold leading-none text-[#061218]"
            style={{ boxShadow: '0 0 0 2px var(--color-bg)' }}
          >
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        // Below 640 px the bell is not at the screen edge, so pin the panel under the 68 px header with an 8 px gutter.
        <div className="absolute right-0 z-50 mt-2 overflow-hidden rounded-xl border border-[var(--color-border-strong)] bg-[var(--color-bg-elevated)] shadow-2xl sm:w-[360px] max-sm:fixed max-sm:inset-x-2 max-sm:top-[76px] max-sm:mt-0 max-sm:flex max-sm:max-h-[calc(100dvh-84px)] max-sm:flex-col">
          <div className="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-3">
            <span className="text-[13px] font-semibold tracking-tight">Notifications</span>
            {unreadCount > 0 && (
              <button
                type="button"
                onClick={handleMarkAll}
                className="text-[11.5px] text-[var(--color-text-muted)] hover:text-[var(--color-accent)]"
              >
                Mark all read
              </button>
            )}
          </div>

          <div className="max-h-[420px] overflow-y-auto">
            {loading ? (
              <p className="px-4 py-6 text-center text-[13px] text-[var(--color-text-muted)]">Loading…</p>
            ) : items.length === 0 ? (
              <p className="px-4 py-8 text-center text-[13px] text-[var(--color-text-muted)]">
                No notifications yet.
              </p>
            ) : (
              items.map((n) => {
                const fmt = formatNotification(n);
                const unread = n.read_at === null;
                return (
                  <button
                    key={n.id}
                    type="button"
                    onClick={() => handleClickItem(n)}
                    className={cn(
                      'flex w-full items-start gap-3 border-b border-[var(--color-border)] px-4 py-3 text-left transition last:border-b-0',
                      unread ? 'bg-[var(--color-accent-dim)]/40' : 'hover:bg-[var(--color-surface)]',
                    )}
                  >
                    <span
                      className={cn(
                        'grid h-7 w-7 shrink-0 place-items-center rounded-full text-[14px]',
                        unread
                          ? 'bg-[var(--color-accent)] text-[#061218]'
                          : 'bg-[var(--color-bg-3)] text-[var(--color-text-muted)]',
                      )}
                    >
                      <NotificationIcon kind={fmt.kind} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className={cn('text-[13px] leading-snug', unread ? 'text-[var(--color-text)]' : 'text-[var(--color-text-soft)]')}>
                        {fmt.text}
                      </p>
                      <p className="font-mono mt-0.5 text-[10.5px] text-[var(--color-text-dim)]">
                        {timeAgo(n.created_at)}
                      </p>
                    </div>
                    {unread && <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-[var(--color-accent)]" />}
                  </button>
                );
              })
            )}
          </div>

          <div className="border-t border-[var(--color-border)] px-4 py-2.5 text-center">
            <Link
              to="/inbox"
              onClick={() => setOpen(false)}
              className="inline-flex items-center gap-1 text-[12px] font-medium text-[var(--color-accent)] hover:underline"
            >
              See all notifications
              <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}

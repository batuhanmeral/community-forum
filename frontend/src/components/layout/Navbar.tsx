import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useStore } from 'react-redux';
import { useAppDispatch, useAppSelector } from '@/app/hooks';
import type { RootState } from '@/app/store';
import { logout, readStoredTokens } from '@/features/auth/authSlice';
import { logoutRequest } from '@/api/auth';
import { withAuthLock } from '@/api/client';
import { syncUnreadCounts } from '@/features/notifications/syncUnreadCounts';
import { usePolling } from '@/lib/usePolling';
import { NotificationDropdown } from '@/components/notifications/NotificationDropdown';
import { Avatar } from '@/components/ui/Avatar';
import { cn } from '@/lib/cn';

const UNREAD_POLL_MS = 30_000;

interface NavbarProps {
  leftOpen?: boolean;
  rightOpen?: boolean;
  onToggleLeft?: () => void;
  onToggleRight?: () => void;
}

const panelLeftIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className="h-[16px] w-[16px]">
    <rect x="3" y="3" width="18" height="18" rx="2" />
    <path d="M9 3v18" />
  </svg>
);
const panelRightIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className="h-[16px] w-[16px]">
    <rect x="3" y="3" width="18" height="18" rx="2" />
    <path d="M15 3v18" />
  </svg>
);

export function Navbar({ leftOpen, rightOpen, onToggleLeft, onToggleRight }: NavbarProps) {
  const { t } = useTranslation();
  const dispatch = useAppDispatch();
  const { getState } = useStore<RootState>();
  const navigate = useNavigate();
  const { user, status } = useAppSelector((s) => s.auth);
  const dmUnread = useAppSelector((s) => s.messaging.dmUnreadCount);
  const notifUnread = useAppSelector((s) => s.notifications.unreadCount);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const [searchParams] = useSearchParams();
  const [query, setQuery] = useState(searchParams.get('q') ?? '');

  // Keep the box in sync when navigating between search result pages.
  useEffect(() => {
    setQuery(searchParams.get('q') ?? '');
  }, [searchParams]);

  // ⌘K / Ctrl+K focuses the search box.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        searchRef.current?.focus();
        searchRef.current?.select();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  function handleSearch(e: FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;
    const type = searchParams.get('type') ?? 'post';
    navigate(`/search?q=${encodeURIComponent(q)}&type=${type}`);
    searchRef.current?.blur();
  }

  const isAuthed = status === 'authenticated';
  const syncCounts = useCallback(() => {
    void syncUnreadCounts(dispatch, getState);
  }, [dispatch, getState]);

  // Sync right away on login, then every 30 s while the tab is visible.
  useEffect(() => {
    if (isAuthed) syncCounts();
  }, [isAuthed, syncCounts]);
  usePolling(syncCounts, UNREAD_POLL_MS, isAuthed);

  // Catch up at once when the user returns to the tab.
  useEffect(() => {
    if (!isAuthed) return;
    const onVisible = () => {
      if (!document.hidden) syncCounts();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
  }, [isAuthed, syncCounts]);

  useEffect(() => {
    if (!menuOpen) return;
    const onClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [menuOpen]);

  async function handleLogout() {
    // Under the refresh lock so a refresh in flight can't store a new session after this logout.
    await withAuthLock(async () => {
      const { refresh } = readStoredTokens();
      if (refresh) await logoutRequest(refresh);
      dispatch(logout());
    });
    setMenuOpen(false);
    navigate('/');
  }

  return (
    <header className="sticky top-0 z-50 border-b border-[var(--color-border)] bg-[rgba(8,8,10,0.72)] backdrop-blur-xl backdrop-saturate-150">
      <div className="mx-auto flex h-[68px] max-w-[1280px] items-center gap-4 px-20 max-[1180px]:px-10 max-[960px]:gap-3 max-[960px]:px-4">
        {/* Left sidebar toggle */}
        {onToggleLeft && (
          <button
            type="button"
            onClick={onToggleLeft}
            title={leftOpen ? 'Hide navigation' : 'Show navigation'}
            className={cn(
              'hidden place-items-center rounded-[8px] p-1.5 transition lg:grid',
              'text-[var(--color-text-dim)] hover:bg-[var(--color-bg-elevated)] hover:text-[var(--color-text)]',
              !leftOpen && 'text-[var(--color-accent)]',
            )}
          >
            {panelLeftIcon}
          </button>
        )}

        <Link to="/" className="flex items-center font-semibold tracking-tight">
          <span className="text-lg">Nexus</span>
        </Link>

        <form
          onSubmit={handleSearch}
          className="mx-auto flex w-full max-w-xl items-center gap-2.5 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-4 py-2.5 transition focus-within:border-[rgba(97,218,251,0.4)] focus-within:bg-[var(--color-bg-3)] focus-within:shadow-[0_0_0_4px_rgba(97,218,251,0.08)]"
        >
          <button type="submit" aria-label="Search" className="shrink-0 text-[var(--color-text-dim)] transition hover:text-[var(--color-accent)]">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" className="h-4 w-4">
              <circle cx="11" cy="11" r="7" />
              <path d="M20 20l-3.5-3.5" />
            </svg>
          </button>
          <input
            ref={searchRef}
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t('nav.searchPlaceholder')}
            className="flex-1 bg-transparent text-sm text-[var(--color-text)] placeholder:text-[var(--color-text-dim)] focus:outline-none"
          />
          <span className="font-mono inline-flex items-center gap-0.5 rounded-md border border-[var(--color-border)] bg-[var(--color-bg-3)] px-1.5 py-0.5 text-[11px] text-[var(--color-text-muted)]">
            ⌘ K
          </span>
        </form>

        <div className="flex items-center justify-end gap-2.5">
          {isAuthed && user ? (
            <>
              <IconButton title={t('nav.messages')} to="/messages" count={dmUnread}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className="h-[18px] w-[18px]">
                  <path d="M4 6h16v11h-7l-4 3v-3H4z" />
                </svg>
              </IconButton>
              <NotificationDropdown unreadCount={notifUnread} />
              <Link
                to="/submit"
                className="btn-primary inline-flex items-center gap-2 rounded-full px-4 py-2 text-[13.5px] font-semibold tracking-tight"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" className="h-[15px] w-[15px]">
                  <path d="M12 5v14m-7-7h14" />
                </svg>
                {t('nav.post')}
              </Link>
              <div ref={menuRef} className="relative">
                <button
                  type="button"
                  onClick={() => setMenuOpen((o) => !o)}
                  className="block"
                  aria-label="Profile menu"
                >
                  <Avatar src={user.avatar} alt={user.username} size="md" />
                </button>
                {menuOpen && (
                  <div className="absolute right-0 mt-2 w-56 overflow-hidden rounded-xl border border-[var(--color-border-strong)] bg-[var(--color-bg-elevated)] shadow-2xl">
                    <div className="px-4 py-2.5 text-xs text-[var(--color-text-muted)]">
                      {t('nav.signedInAs')} <span className="font-semibold text-[var(--color-text)]">{user.username}</span>
                      <div className="font-mono mt-1 flex gap-3 text-[11px] text-[var(--color-text-dim)]">
                        <span>↑ <span className="text-[var(--color-accent)]">{user.post_karma + user.comment_karma}</span> {t('nav.karma')}</span>
                      </div>
                    </div>
                    <div className="border-t border-[var(--color-border)]" />
                    <Link to={`/u/${user.username}`} onClick={() => setMenuOpen(false)} className="block px-4 py-2.5 text-sm hover:bg-[var(--color-surface-hover)]">
                      {t('nav.profile')}
                    </Link>
                    <Link to="/settings" onClick={() => setMenuOpen(false)} className="block px-4 py-2.5 text-sm hover:bg-[var(--color-surface-hover)]">
                      {t('nav.settings')}
                    </Link>
                    <div className="border-t border-[var(--color-border)]" />
                    <button
                      type="button"
                      onClick={handleLogout}
                      className="block w-full px-4 py-2.5 text-left text-sm text-[var(--color-danger)] hover:bg-[var(--color-surface-hover)]"
                    >
                      {t('nav.logout')}
                    </button>
                  </div>
                )}
              </div>
            </>
          ) : (
            <>
              <Link
                to="/login"
                className="inline-flex items-center gap-1.5 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-4 py-2 text-sm font-medium text-[var(--color-text-soft)] transition hover:bg-[var(--color-bg-3)] hover:text-[var(--color-text)]"
              >
                {t('nav.login')}
              </Link>
              <Link
                to="/register"
                className="btn-primary hidden items-center gap-2 rounded-full px-4 py-2 text-[13.5px] font-semibold tracking-tight sm:inline-flex"
              >
                {t('nav.signup')}
              </Link>
            </>
          )}

          {/* Right sidebar toggle */}
          {onToggleRight && (
            <button
              type="button"
              onClick={onToggleRight}
              title={rightOpen ? 'Hide sidebar' : 'Show sidebar'}
              className={cn(
                'hidden place-items-center rounded-[8px] p-1.5 transition lg:grid',
                'text-[var(--color-text-dim)] hover:bg-[var(--color-bg-elevated)] hover:text-[var(--color-text)]',
                !rightOpen && 'text-[var(--color-accent)]',
              )}
            >
              {panelRightIcon}
            </button>
          )}
        </div>
      </div>

      <style>{`
        .btn-primary {
          background: var(--color-accent);
          color: #061218;
          box-shadow: 0 4px 16px rgba(97, 218, 251, 0.28), inset 0 1px 0 rgba(255,255,255,0.4);
          transition: transform 0.1s ease, box-shadow 0.15s ease;
        }
        .btn-primary:hover {
          transform: translateY(-1px);
          box-shadow: 0 6px 22px rgba(97, 218, 251, 0.4), inset 0 1px 0 rgba(255,255,255,0.4);
        }
        .btn-primary:active { transform: translateY(0); }
      `}</style>
    </header>
  );
}

interface IconButtonProps {
  title: string;
  count?: number;
  to?: string;
  children: React.ReactNode;
}

function IconButton({ title, count, to, children }: IconButtonProps) {
  const className = cn(
    'relative grid h-[38px] w-[38px] place-items-center rounded-[11px]',
    'text-[var(--color-text-soft)] transition hover:bg-[var(--color-bg-elevated)] hover:text-[var(--color-text)]',
  );
  const inner = (
    <>
      {children}
      {count !== undefined && count > 0 ? (
        <span
          className="font-mono absolute -right-1 -top-1 inline-flex h-4 min-w-[16px] items-center justify-center rounded-full bg-[var(--color-accent)] px-1 text-[10px] font-bold leading-none text-[#061218]"
          style={{ boxShadow: '0 0 0 2px var(--color-bg)' }}
        >
          {count > 99 ? '99+' : count}
        </span>
      ) : null}
    </>
  );
  if (to) {
    return (
      <Link to={to} title={title} className={className} aria-label={title}>
        {inner}
      </Link>
    );
  }
  return (
    <button type="button" title={title} className={className}>
      {inner}
    </button>
  );
}

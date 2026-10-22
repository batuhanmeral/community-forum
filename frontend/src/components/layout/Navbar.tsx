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
import { userPath } from '@/lib/paths';
import { usePolling } from '@/lib/usePolling';
import { NotificationDropdown } from '@/components/notifications/NotificationDropdown';
import { Avatar } from '@/components/ui/Avatar';
import { buttonClasses } from '@/components/ui/Button';
import { APP_NAME } from '@/components/ui/PageTitle';
import { cn } from '@/lib/cn';
import { ArrowBigUp, Menu, MessageSquare, PanelLeft, PanelRight, Plus, Search } from 'lucide-react';

const UNREAD_POLL_MS = 30_000;

interface NavbarProps {
  leftOpen?: boolean;
  rightOpen?: boolean;
  onToggleLeft?: () => void;
  onToggleRight?: () => void;
  onOpenMenu?: () => void;
}

const panelLeftIcon = (
  <PanelLeft className="h-[16px] w-[16px]" />
);
const panelRightIcon = (
  <PanelRight className="h-[16px] w-[16px]" />
);

const menuIcon = (
  <Menu className="h-[18px] w-[18px]" />
);
const searchIcon = (
  <Search className="h-4 w-4" />
);

export function Navbar({ leftOpen, rightOpen, onToggleLeft, onToggleRight, onOpenMenu }: NavbarProps) {
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
  const mobileSearchRef = useRef<HTMLInputElement>(null);
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false);
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

  useEffect(() => {
    if (mobileSearchOpen) mobileSearchRef.current?.focus();
  }, [mobileSearchOpen]);

  function handleSearch(e: FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;
    const type = searchParams.get('type') ?? 'post';
    navigate(`/search?q=${encodeURIComponent(q)}&type=${type}`);
    searchRef.current?.blur();
    mobileSearchRef.current?.blur();
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
    <header className="sticky top-0 z-50 border-b border-[var(--color-border)] bg-[var(--color-bg)]">
      <div className="mx-auto flex h-[68px] max-w-[1280px] items-center gap-4 px-20 max-[1180px]:px-10 max-[960px]:gap-3 max-[960px]:px-4 max-sm:gap-2">
        {onOpenMenu && (
          <button
            type="button"
            onClick={onOpenMenu}
            aria-label={t('nav.openMenu')}
            className="grid h-[38px] w-[38px] shrink-0 place-items-center rounded-[11px] text-[var(--color-text-soft)] transition hover:bg-[var(--color-bg-elevated)] hover:text-[var(--color-text)] min-[960px]:hidden"
          >
            {menuIcon}
          </button>
        )}

        {/* Left sidebar toggle */}
        {onToggleLeft && (
          <button
            type="button"
            onClick={onToggleLeft}
            title={leftOpen ? t('nav.hideNavigation') : t('nav.showNavigation')}
            className={cn(
              'hidden place-items-center rounded-[8px] p-1.5 transition min-[960px]:grid',
              'text-[var(--color-text-dim)] hover:bg-[var(--color-bg-elevated)] hover:text-[var(--color-text)]',
              !leftOpen && 'text-[var(--color-accent)]',
            )}
          >
            {panelLeftIcon}
          </button>
        )}

        <Link to="/" className="flex shrink-0 items-center font-semibold tracking-tight">
          <span className="text-lg">{APP_NAME}</span>
        </Link>

        <SearchForm
          inputRef={searchRef}
          value={query}
          onChange={setQuery}
          onSubmit={handleSearch}
          className="mx-auto hidden max-w-xl sm:flex"
        />

        <div className="flex items-center justify-end gap-2.5 max-sm:ml-auto max-sm:gap-1">
          <button
            type="button"
            onClick={() => setMobileSearchOpen((o) => !o)}
            aria-label={t('nav.openSearch')}
            aria-expanded={mobileSearchOpen}
            className={cn(
              'grid h-[38px] w-[38px] place-items-center rounded-[11px] transition sm:hidden',
              'text-[var(--color-text-soft)] hover:bg-[var(--color-bg-elevated)] hover:text-[var(--color-text)]',
              mobileSearchOpen && 'bg-[var(--color-bg-elevated)] text-[var(--color-text)]',
            )}
          >
            {searchIcon}
          </button>
          {isAuthed && user ? (
            <>
              <IconButton title={t('nav.messages')} to="/messages" count={dmUnread}>
                <MessageSquare className="h-[18px] w-[18px]" />
              </IconButton>
              <NotificationDropdown unreadCount={notifUnread} />
              <Link
                to="/submit"
                className={cn(buttonClasses({ size: 'md' }), 'tracking-tight max-[480px]:px-2.5')}
              >
                <Plus strokeWidth={2.2} className="h-[15px] w-[15px]" />
                <span className="max-[480px]:sr-only">{t('nav.post')}</span>
              </Link>
              <div ref={menuRef} className="relative">
                <button
                  type="button"
                  onClick={() => setMenuOpen((o) => !o)}
                  className="block"
                  aria-label={t('nav.profileMenu')}
                >
                  <Avatar src={user.avatar} alt={user.username} size="md" />
                </button>
                {menuOpen && (
                  <div className="absolute right-0 mt-2 w-56 overflow-hidden rounded-xl border border-[var(--color-border-strong)] bg-[var(--color-bg-elevated)] shadow-md">
                    <div className="px-4 py-2.5 text-xs text-[var(--color-text-muted)]">
                      {t('nav.signedInAs')} <span className="font-semibold text-[var(--color-text)]">{user.username}</span>
                      <div className="font-mono mt-1 flex gap-3 text-[11px] text-[var(--color-text-dim)]">
                        <span className="inline-flex items-center gap-0.5"><ArrowBigUp className="h-3.5 w-3.5" /><span className="text-[var(--color-accent)]">{user.post_karma + user.comment_karma}</span> {t('nav.karma')}</span>
                      </div>
                    </div>
                    <div className="border-t border-[var(--color-border)]" />
                    <Link to={userPath(user.username)} onClick={() => setMenuOpen(false)} className="block px-4 py-2.5 text-sm hover:bg-[var(--color-surface-hover)]">
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
          ) : isAuthed ? (
            // Signed in but the profile has not loaded: "Log in" here would loop back via LoginPage.
            <span role="status" className="grid h-10 w-10 shrink-0 rounded-full bg-[var(--color-bg-3)]">
              <span className="sr-only">{t('nav.loadingAccount')}</span>
            </span>
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
                className={cn(buttonClasses({ size: 'md' }), 'tracking-tight max-sm:hidden')}
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
              title={rightOpen ? t('nav.hideSidebar') : t('nav.showSidebar')}
              className={cn(
                'hidden place-items-center rounded-[8px] p-1.5 transition min-[960px]:grid',
                'text-[var(--color-text-dim)] hover:bg-[var(--color-bg-elevated)] hover:text-[var(--color-text)]',
                !rightOpen && 'text-[var(--color-accent)]',
              )}
            >
              {panelRightIcon}
            </button>
          )}
        </div>
      </div>

      {mobileSearchOpen && (
        <div className="px-4 pb-3 sm:hidden">
          <SearchForm
            inputRef={mobileSearchRef}
            value={query}
            onChange={setQuery}
            onSubmit={handleSearch}
            className="flex"
          />
        </div>
      )}
    </header>
  );
}

interface SearchFormProps {
  inputRef: React.Ref<HTMLInputElement>;
  value: string;
  onChange: (value: string) => void;
  onSubmit: (e: FormEvent) => void;
  className?: string;
}

function SearchForm({ inputRef, value, onChange, onSubmit, className }: SearchFormProps) {
  const { t } = useTranslation();
  return (
    <form
      onSubmit={onSubmit}
      className={cn(
        'w-full items-center gap-2.5 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-4 py-2.5 transition focus-within:border-[var(--color-accent)]/40 focus-within:bg-[var(--color-bg-3)]',
        className,
      )}
    >
      <button type="submit" aria-label={t('nav.search')} className="shrink-0 text-[var(--color-text-dim)] transition hover:text-[var(--color-accent)]">
        {searchIcon}
      </button>
      <input
        ref={inputRef}
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={t('nav.searchPlaceholder')}
        className="min-w-0 flex-1 bg-transparent text-sm text-[var(--color-text)] placeholder:text-[var(--color-text-dim)] focus:outline-none"
      />
      <span className="font-mono inline-flex items-center gap-0.5 rounded-md border border-[var(--color-border)] bg-[var(--color-bg-3)] px-1.5 py-0.5 text-[11px] text-[var(--color-text-muted)] max-[960px]:hidden">
        ⌘ K
      </span>
    </form>
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
          className="font-mono absolute -right-1 -top-1 inline-flex h-4 min-w-[16px] items-center justify-center rounded-full bg-[var(--color-accent)] px-1 text-[10px] font-bold leading-none text-[var(--color-on-accent)]"
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

import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from '@/app/hooks';
import { logout } from '@/features/auth/authSlice';
import { logoutRequest } from '@/api/auth';
import { Avatar } from '@/components/ui/Avatar';
import { cn } from '@/lib/cn';

export function Navbar() {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const { user, refreshToken, status } = useAppSelector((s) => s.auth);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

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
    if (refreshToken) await logoutRequest(refreshToken);
    dispatch(logout());
    setMenuOpen(false);
    navigate('/');
  }

  const isAuthed = status === 'authenticated';

  return (
    <header className="sticky top-0 z-50 border-b border-[var(--color-border)] bg-[rgba(8,8,10,0.72)] backdrop-blur-xl backdrop-saturate-150">
      <div className="mx-auto grid h-[68px] max-w-[1480px] grid-cols-[280px_minmax(0,1fr)_340px] items-center gap-7 px-8 max-[1180px]:grid-cols-[240px_minmax(0,1fr)_300px] max-[1180px]:gap-5 max-[1180px]:px-5 max-[960px]:flex max-[960px]:gap-3 max-[960px]:px-4">
        <Link to="/" className="flex items-center gap-2.5 font-semibold tracking-tight">
          <span className="brand-mark relative grid h-8 w-8 place-items-center rounded-[9px] text-[16px] font-bold text-[#061218]">
            N
          </span>
          <span className="text-lg">
            Nexus<span className="text-[var(--color-accent)]">.</span>
          </span>
        </Link>

        <div className="mx-auto flex w-full max-w-xl items-center gap-2.5 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-4 py-2.5 transition focus-within:border-[rgba(97,218,251,0.4)] focus-within:bg-[var(--color-bg-3)] focus-within:shadow-[0_0_0_4px_rgba(97,218,251,0.08)]">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" className="h-4 w-4 shrink-0 text-[var(--color-text-dim)]">
            <circle cx="11" cy="11" r="7" />
            <path d="M20 20l-3.5-3.5" />
          </svg>
          <input
            type="search"
            placeholder="Search Nexus — communities, posts, people…"
            className="flex-1 bg-transparent text-sm text-[var(--color-text)] placeholder:text-[var(--color-text-dim)] focus:outline-none"
          />
          <span className="font-mono inline-flex items-center gap-0.5 rounded-md border border-[var(--color-border)] bg-[var(--color-bg-3)] px-1.5 py-0.5 text-[11px] text-[var(--color-text-muted)]">
            ⌘ K
          </span>
        </div>

        <div className="flex items-center justify-end gap-2.5">
          {isAuthed && user ? (
            <>
              <IconButton title="Messages">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className="h-[18px] w-[18px]">
                  <path d="M4 6h16v11h-7l-4 3v-3H4z" />
                </svg>
              </IconButton>
              <IconButton title="Notifications" dot>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className="h-[18px] w-[18px]">
                  <path d="M6 8a6 6 0 1 1 12 0c0 5 2 6 2 6H4s2-1 2-6zM10 19a2 2 0 0 0 4 0" />
                </svg>
              </IconButton>
              <Link
                to="/submit"
                className="btn-primary inline-flex items-center gap-2 rounded-full px-4 py-2 text-[13.5px] font-semibold tracking-tight"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" className="h-[15px] w-[15px]">
                  <path d="M12 5v14m-7-7h14" />
                </svg>
                Post
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
                      Signed in as <span className="font-semibold text-[var(--color-text)]">{user.username}</span>
                    </div>
                    <div className="border-t border-[var(--color-border)]" />
                    <Link to={`/u/${user.username}`} onClick={() => setMenuOpen(false)} className="block px-4 py-2.5 text-sm hover:bg-[var(--color-surface-hover)]">
                      Profile
                    </Link>
                    <Link to="/settings" onClick={() => setMenuOpen(false)} className="block px-4 py-2.5 text-sm hover:bg-[var(--color-surface-hover)]">
                      Settings
                    </Link>
                    <div className="border-t border-[var(--color-border)]" />
                    <button
                      type="button"
                      onClick={handleLogout}
                      className="block w-full px-4 py-2.5 text-left text-sm text-[var(--color-danger)] hover:bg-[var(--color-surface-hover)]"
                    >
                      Log out
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
                Log in
              </Link>
              <Link
                to="/register"
                className="btn-primary hidden items-center gap-2 rounded-full px-4 py-2 text-[13.5px] font-semibold tracking-tight sm:inline-flex"
              >
                Sign up
              </Link>
            </>
          )}
        </div>
      </div>

      <style>{`
        .brand-mark {
          background: linear-gradient(135deg, var(--color-accent) 0%, #2faed0 100%);
          box-shadow: 0 4px 18px rgba(97, 218, 251, 0.35), inset 0 1px 0 rgba(255,255,255,0.4);
        }
        .brand-mark::after {
          content: '';
          position: absolute;
          inset: 0;
          border-radius: 9px;
          border: 1px solid rgba(255,255,255,0.15);
          pointer-events: none;
        }
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
  dot?: boolean;
  children: React.ReactNode;
}

function IconButton({ title, dot, children }: IconButtonProps) {
  return (
    <button
      type="button"
      title={title}
      className={cn(
        'relative grid h-[38px] w-[38px] place-items-center rounded-[11px]',
        'text-[var(--color-text-soft)] transition hover:bg-[var(--color-bg-elevated)] hover:text-[var(--color-text)]',
      )}
    >
      {children}
      {dot && (
        <span
          className="absolute right-[9px] top-[9px] block h-[7px] w-[7px] rounded-full bg-[var(--color-accent)]"
          style={{ boxShadow: '0 0 0 2px var(--color-bg), 0 0 8px var(--color-accent-glow)' }}
        />
      )}
    </button>
  );
}

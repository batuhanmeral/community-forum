import { Link, NavLink } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/cn';

export function Navbar() {
  return (
    <header className="sticky top-0 z-40 border-b border-[var(--color-border)] bg-[var(--color-bg)]/85 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-[1400px] items-center gap-4 px-4 sm:px-6 lg:px-8">
        <Link to="/" className="flex items-center gap-2 shrink-0">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-[var(--color-accent)] text-[#0b1418] font-black">
            N
          </span>
          <span className="hidden text-lg font-bold tracking-tight sm:inline">nexus</span>
        </Link>

        <div className="flex-1 max-w-xl">
          <div className="relative">
            <input
              type="search"
              placeholder="Search nexus..."
              className="h-10 w-full rounded-full border border-[var(--color-border)] bg-[var(--color-bg-elevated)] pl-10 pr-4 text-sm placeholder:text-[var(--color-text-dim)] focus:border-[var(--color-accent)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]/25"
            />
            <svg
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-text-dim)]"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <circle cx="11" cy="11" r="7" />
              <path d="m20 20-3.5-3.5" />
            </svg>
          </div>
        </div>

        <nav className="hidden items-center gap-1 md:flex">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              cn(
                'px-3 py-2 rounded-full text-sm transition-colors',
                isActive
                  ? 'text-[var(--color-text)] bg-[var(--color-surface)]'
                  : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]',
              )
            }
          >
            Home
          </NavLink>
          <NavLink
            to="/explore"
            className={({ isActive }) =>
              cn(
                'px-3 py-2 rounded-full text-sm transition-colors',
                isActive
                  ? 'text-[var(--color-text)] bg-[var(--color-surface)]'
                  : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]',
              )
            }
          >
            Explore
          </NavLink>
        </nav>

        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm">
            Log in
          </Button>
          <Button variant="primary" size="sm" className="hidden sm:inline-flex">
            Sign up
          </Button>
        </div>
      </div>
    </header>
  );
}

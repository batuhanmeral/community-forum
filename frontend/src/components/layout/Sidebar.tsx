import { NavLink } from 'react-router-dom';
import { cn } from '@/lib/cn';

interface NavItem {
  to: string;
  label: string;
  icon: React.ReactNode;
}

const homeIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <path d="M3 11.5 12 4l9 7.5" />
    <path d="M5 10v10h14V10" />
  </svg>
);

const popularIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <path d="M12 3v18" />
    <path d="m6 13 6-6 6 6" />
  </svg>
);

const exploreIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.5-3.5" />
  </svg>
);

const allIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <rect x="3" y="4" width="18" height="4" rx="1.5" />
    <rect x="3" y="10" width="18" height="4" rx="1.5" />
    <rect x="3" y="16" width="18" height="4" rx="1.5" />
  </svg>
);

const items: NavItem[] = [
  { to: '/', label: 'Home', icon: homeIcon },
  { to: '/popular', label: 'Popular', icon: popularIcon },
  { to: '/explore', label: 'Explore', icon: exploreIcon },
  { to: '/all', label: 'All', icon: allIcon },
];

export function Sidebar() {
  return (
    <aside className="hidden w-64 shrink-0 lg:block">
      <nav className="sticky top-[72px] flex flex-col gap-1 pr-2">
        <div className="px-3 pb-2 pt-1 text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-dim)]">
          Feeds
        </div>
        {items.map((it) => (
          <NavLink
            key={it.to}
            to={it.to}
            end={it.to === '/'}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors',
                isActive
                  ? 'bg-[var(--color-surface)] text-[var(--color-text)]'
                  : 'text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text)]',
              )
            }
          >
            <span className="h-5 w-5">{it.icon}</span>
            <span>{it.label}</span>
          </NavLink>
        ))}

        <div className="my-3 border-t border-[var(--color-border)]" />

        <div className="px-3 pb-2 pt-1 text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-dim)]">
          Communities
        </div>
        <p className="px-3 text-xs text-[var(--color-text-dim)]">
          Your subscribed communities will appear here.
        </p>
      </nav>
    </aside>
  );
}

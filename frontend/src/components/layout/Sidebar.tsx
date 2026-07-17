import { useEffect, useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { listCommunities } from '@/api/communities';
import type { Community } from '@/features/communities/types';
import { useAppSelector } from '@/app/hooks';
import { cn } from '@/lib/cn';

interface NavItem {
  to: string;
  label: string;
  icon: React.ReactNode;
}

const homeIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-7h-6v7H4a1 1 0 0 1-1-1z" />
  </svg>
);
const compassIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="9" />
    <path d="M16 8l-2 6-6 2 2-6z" />
  </svg>
);
const trendIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 17l6-6 4 4 8-9M14 6h7v7" />
  </svg>
);
const globeIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="9" />
    <path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" />
  </svg>
);
const bookmarkIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
    <path d="M6 4h12v17l-6-4-6 4z" />
  </svg>
);
const clockIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </svg>
);
const settingsIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="3" />
    <circle cx="12" cy="12" r="9" />
  </svg>
);
const sparkleIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 3v6m0 6v6M3 12h6m6 0h6M6 6l4 4m4 4l4 4M18 6l-4 4m-4 4l-4 4" />
  </svg>
);
const plusIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 5v14m-7-7h14" />
  </svg>
);

const navItems: NavItem[] = [
  { to: '/', label: 'Home', icon: homeIcon },
  { to: '/explore', label: 'Explore', icon: compassIcon },
  { to: '/popular', label: 'Popular', icon: trendIcon },
  { to: '/all', label: 'All', icon: globeIcon },
];

const personalItems: NavItem[] = [
  { to: '/saved', label: 'Saved', icon: bookmarkIcon },
  { to: '/history', label: 'History', icon: clockIcon },
];

export function Sidebar() {
  const isAuthed = useAppSelector((s) => s.auth.status === 'authenticated');
  const [myCommunities, setMyCommunities] = useState<Community[]>([]);
  const location = useLocation();

  useEffect(() => {
    if (!isAuthed) return;
    listCommunities({ ordering: '-member_count' })
      .then((d) => setMyCommunities(d.results.filter((c) => c.is_member).slice(0, 8)))
      .catch(() => undefined);
  }, [isAuthed, location.pathname]);

  return (
    <aside className="sticky top-[88px] hidden h-[calc(100vh-110px)] flex-col overflow-y-auto pb-10 pr-1 pt-5 max-[960px]:hidden lg:flex">
      <SidebarSection>
        {navItems.map((it) => (
          <SidebarItem key={it.to} {...it} />
        ))}
      </SidebarSection>

      {isAuthed && (
        <SidebarSection title="Your feed">
          {personalItems.map((it) => (
            <SidebarItem key={it.to} {...it} />
          ))}
        </SidebarSection>
      )}

      <SidebarSection
        title="Communities"
        action={
          isAuthed ? (
            <NavLink to="/c/create" className="text-[11px] text-[var(--color-text-dim)] hover:text-[var(--color-accent)]">
              + New
            </NavLink>
          ) : null
        }
      >
        <SidebarItem to="/c" label="Browse all" icon={globeIcon} />
        {myCommunities.map((c) => (
          <CommunityItem key={c.id} community={c} />
        ))}
      </SidebarSection>

      <SidebarSection title="Resources">
        <SidebarItem to="/settings" label="Settings" icon={settingsIcon} />
        <SidebarItem to="/whats-new" label="What's new" icon={sparkleIcon} suffix={<span className="font-mono text-[11px] text-[var(--color-accent)]">v0.1</span>} />
      </SidebarSection>

      {!isAuthed && (
        <NavLink
          to="/register"
          className="mx-2.5 mt-1.5 inline-flex h-8 w-fit items-center justify-center gap-1.5 self-start rounded-full bg-[var(--color-accent)] px-3.5 text-[12.5px] font-semibold text-[#061218]"
          style={{ boxShadow: '0 4px 16px rgba(97, 218, 251, 0.28), inset 0 1px 0 rgba(255,255,255,0.4)' }}
        >
          <span className="h-[13px] w-[13px]">{plusIcon}</span>
          Create account
        </NavLink>
      )}
    </aside>
  );
}

function SidebarSection({ title, children, action }: { title?: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="mb-3.5">
      {title && (
        <div className="mb-1.5 flex items-center justify-between px-3 text-[10.5px] font-medium uppercase tracking-[0.12em] text-[var(--color-text-dim)]">
          <span>{title}</span>
          {action}
        </div>
      )}
      <div className="flex flex-col">{children}</div>
    </div>
  );
}

function SidebarItem({ to, label, icon, suffix }: NavItem & { suffix?: React.ReactNode }) {
  return (
    <NavLink
      to={to}
      end={to === '/'}
      className={({ isActive }) =>
        cn(
          'group relative flex w-[170px] items-center gap-2.5 rounded-[8px] px-3 py-[7px] text-[13.5px] font-normal transition-all',
          isActive
            ? 'text-white'
            : 'text-[rgba(255,255,255,0.7)] hover:text-white',
        )
      }
    >
      {({ isActive }) => (
        <>
          {isActive && (
            <span
              className="absolute -left-1.5 top-1/2 h-[16px] w-[2.5px] -translate-y-1/2 rounded-full bg-[var(--color-accent)]"
              style={{ boxShadow: '0 0 12px var(--color-accent-glow)' }}
            />
          )}
          <span className="grid h-[22px] w-[22px] place-items-center">
            <span className="h-[13px] w-[13px]">{icon}</span>
          </span>
          <span className="truncate">{label}</span>
          {suffix}
        </>
      )}
    </NavLink>
  );
}

function CommunityItem({ community }: { community: Community }) {
  return (
    <NavLink
      to={`/c/${community.slug}`}
      className={({ isActive }) =>
        cn(
          'flex w-[170px] items-center gap-2.5 rounded-[8px] px-3 py-[7px] text-[13.5px] transition-all',
          isActive
            ? 'text-white'
            : 'text-[rgba(255,255,255,0.7)] hover:text-white',
        )
      }
    >
      <span
        className="grid h-[22px] w-[22px] place-items-center rounded-full border border-[var(--color-border)] text-[11px] font-semibold text-[var(--color-accent)]"
        style={{ background: 'linear-gradient(135deg, #2a3540, #1a2128)' }}
      >
        {community.slug[0]?.toUpperCase()}
      </span>
      <span className="flex-1 truncate">c/{community.slug}</span>
      <span className="font-mono text-[10.5px] text-[var(--color-text-dim)]">
        {formatCount(community.member_count)}
      </span>
    </NavLink>
  );
}

function formatCount(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, '') + 'k';
  return String(n);
}

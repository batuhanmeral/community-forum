import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { NavLink } from 'react-router-dom';
import { listCommunities } from '@/api/communities';
import type { Community } from '@/features/communities/types';
import { useAppSelector } from '@/app/hooks';
import { cn } from '@/lib/cn';
import { Bookmark, Globe, Home, Plus, Settings, TrendingUp } from 'lucide-react';

interface NavItem {
  to: string;
  label: string;
  icon: React.ReactNode;
}

const homeIcon = (
  <Home className="h-full w-full" />
);
const trendIcon = (
  <TrendingUp className="h-full w-full" />
);
const globeIcon = (
  <Globe className="h-full w-full" />
);
const bookmarkIcon = (
  <Bookmark className="h-full w-full" />
);
const settingsIcon = (
  <Settings className="h-full w-full" />
);
const plusIcon = (
  <Plus className="h-full w-full" />
);

const navItems: NavItem[] = [
  { to: '/', label: 'sidebar.home', icon: homeIcon },
  { to: '/popular', label: 'sidebar.popular', icon: trendIcon },
  { to: '/all', label: 'sidebar.all', icon: globeIcon },
];

const personalItems: NavItem[] = [
  { to: '/saved', label: 'sidebar.saved', icon: bookmarkIcon },
];

export function Sidebar() {
  return (
    <aside className="sticky top-[88px] flex h-[calc(100vh-110px)] flex-col overflow-y-auto pb-10 pr-1 pt-5">
      <SidebarNav />
    </aside>
  );
}

export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const { t } = useTranslation();
  const isAuthed = useAppSelector((s) => s.auth.status === 'authenticated');
  const [myCommunities, setMyCommunities] = useState<Community[]>([]);
  const membershipsVersion = useAppSelector((s) => s.memberships.version);

  useEffect(() => {
    if (!isAuthed) {
      setMyCommunities([]);
      return;
    }
    // A response that lands after logout or a newer fetch belongs to a stale session.
    let active = true;
    listCommunities({ joined: true, ordering: '-member_count', page_size: 8 })
      .then((d) => {
        if (active) setMyCommunities(d.results);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [isAuthed, membershipsVersion]);

  return (
    <>
      <SidebarSection>
        {navItems.map((it) => (
          <SidebarItem key={it.to} {...it} label={t(it.label)} onNavigate={onNavigate} />
        ))}
      </SidebarSection>

      {isAuthed && (
        <SidebarSection title={t('sidebar.yourFeed')}>
          {personalItems.map((it) => (
            <SidebarItem key={it.to} {...it} label={t(it.label)} onNavigate={onNavigate} />
          ))}
        </SidebarSection>
      )}

      <SidebarSection
        title={t('sidebar.communities')}
        action={
          isAuthed ? (
            <NavLink
              to="/c/create"
              onClick={onNavigate}
              className="text-[11px] text-[var(--color-text-dim)] hover:text-[var(--color-accent)]"
            >
              {t('sidebar.new')}
            </NavLink>
          ) : null
        }
      >
        <SidebarItem to="/c" label={t('sidebar.browseAll')} icon={globeIcon} onNavigate={onNavigate} />
        {myCommunities.map((c) => (
          <CommunityItem key={c.id} community={c} onNavigate={onNavigate} />
        ))}
      </SidebarSection>

      <SidebarSection title={t('sidebar.resources')}>
        <SidebarItem to="/settings" label={t('sidebar.settings')} icon={settingsIcon} onNavigate={onNavigate} />
      </SidebarSection>

      {!isAuthed && (
        <NavLink
          to="/register"
          onClick={onNavigate}
          className="mx-2.5 mt-1.5 inline-flex h-8 w-fit items-center justify-center gap-1.5 self-start rounded-full bg-[var(--color-accent)] px-3.5 text-[12.5px] font-semibold text-[#061218]"
          style={{ boxShadow: '0 4px 16px rgba(97, 218, 251, 0.28), inset 0 1px 0 rgba(255,255,255,0.4)' }}
        >
          <span className="h-[13px] w-[13px]">{plusIcon}</span>
          {t('sidebar.createAccount')}
        </NavLink>
      )}
    </>
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

function SidebarItem({
  to,
  label,
  icon,
  suffix,
  onNavigate,
}: NavItem & { suffix?: React.ReactNode; onNavigate?: () => void }) {
  return (
    <NavLink
      to={to}
      end={to === '/'}
      onClick={onNavigate}
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

function CommunityItem({ community, onNavigate }: { community: Community; onNavigate?: () => void }) {
  return (
    <NavLink
      to={`/c/${community.slug}`}
      onClick={onNavigate}
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

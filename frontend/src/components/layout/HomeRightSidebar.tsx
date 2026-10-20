import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { trendingCommunities, trendingPosts } from '@/api/trending';
import { joinCommunity, leaveCommunity } from '@/api/communities';
import { getLeaderboard, type UserProfile } from '@/api/users';
import type { Community } from '@/features/communities/types';
import type { Post } from '@/features/posts/types';
import { membershipsChanged } from '@/features/communities/membershipsSlice';
import { useAppDispatch, useAppSelector } from '@/app/hooks';
import { userPath } from '@/lib/paths';
import { timeAgo } from '@/lib/time';
import { cn } from '@/lib/cn';
import { Badge } from '@/components/ui/Badge';
import { ArrowBigUp, ArrowRight, Plus } from 'lucide-react';

export function HomeRightSidebar() {
  const { t } = useTranslation();
  const isAuthed = useAppSelector((s) => s.auth.status === 'authenticated');
  const [trendPosts, setTrendPosts] = useState<Post[]>([]);
  const [topComms, setTopComms] = useState<Community[]>([]);
  const [topUsers, setTopUsers] = useState<UserProfile[]>([]);

  useEffect(() => {
    trendingPosts()
      .then((p) => setTrendPosts(p.slice(0, 5)))
      .catch(() => undefined);
    trendingCommunities()
      .then((c) => setTopComms(c.slice(0, 5)))
      .catch(() => undefined);
    getLeaderboard()
      .then((u) => setTopUsers(u.slice(0, 5)))
      .catch(() => undefined);
  }, []);

  return (
    <aside className="sticky top-[88px] hidden h-[calc(100vh-110px)] flex-col gap-3.5 overflow-y-auto pb-10 pl-1 pt-5 lg:flex">
      {/* Trending */}
      <Card>
        <CardHead title={<><span className="live-dot" /> {t('rightbar.trendingNow')}</>} more="/popular" />
        {trendPosts.length === 0 ? (
          <p className="px-4 py-2.5 text-[12.5px] text-[var(--color-text-muted)]">{t('rightbar.noTrending')}</p>
        ) : (
          trendPosts.map((p, i) => (
            <Link
              key={p.id}
              to={`/posts/${p.id}`}
              className="flex gap-2.5 border-t border-[var(--color-border)] px-4 py-2.5 text-[12.5px] transition hover:bg-[var(--color-surface)]"
            >
              <span className={cn('font-mono w-[16px] shrink-0 pt-0.5 text-[11px]', i < 3 ? 'text-[var(--color-accent)]' : 'text-[var(--color-text-dim)]')}>
                {String(i + 1).padStart(2, '0')}
              </span>
              <div className="min-w-0 flex-1">
                <div className="mb-0.5 text-[10px] uppercase tracking-[0.08em] text-[var(--color-text-dim)]">
                  c/{p.community} · {t('rightbar.hot')}
                </div>
                <div className="line-clamp-2 text-[13px] font-medium leading-snug text-[var(--color-text)]">
                  {p.title}
                </div>
                <div className="font-mono mt-0.5 text-[10.5px] text-[var(--color-text-dim)]">
                  {p.score} {t('rightbar.pts')} · {timeAgo(p.created_at)}
                </div>
              </div>
            </Link>
          ))
        )}
      </Card>

      {/* Top communities */}
      <Card>
        <CardHead title={t('rightbar.topCommunities')} more="/c" />
        {topComms.length === 0 ? (
          <p className="px-4 py-2.5 text-[12.5px] text-[var(--color-text-muted)]">{t('rightbar.noCommunities')}</p>
        ) : (
          topComms.map((c, i) => <CommunityRow key={c.id} community={c} rank={i + 1} />)
        )}
      </Card>

      {/* Karma leaderboard */}
      {topUsers.length > 0 && (
        <Card>
          <CardHead title={t('rightbar.karmaLeaders')} />
          {topUsers.map((u, i) => (
            <Link
              key={u.id}
              to={userPath(u.username)}
              className="flex items-center gap-2.5 border-t border-[var(--color-border)] px-4 py-2 text-[12.5px] transition hover:bg-[var(--color-surface)]"
            >
              <span className={cn('font-mono w-3 text-[10.5px]', i === 0 ? 'text-[var(--color-accent)]' : 'text-[var(--color-text-dim)]')}>
                {i + 1}
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-[13px] font-medium text-[var(--color-text)]">
                  u/{u.username}
                </div>
              </div>
              <span className="font-mono text-[10.5px] text-[var(--color-text-dim)]">
                <span className="inline-flex items-center gap-0.5"><ArrowBigUp className="h-3 w-3" />{formatCount(u.total_karma)}</span>
              </span>
            </Link>
          ))}
        </Card>
      )}

      {/* Quick create */}
      <Card>
        <div className="px-4 py-3.5">
          <Link
            to={isAuthed ? '/c/create' : '/register'}
            className="inline-flex w-full items-center justify-center gap-1.5 rounded-full bg-[var(--color-accent)] px-3.5 py-[7px] text-[12.5px] font-semibold text-[#061218]"
            style={{ boxShadow: '0 4px 16px rgba(97, 218, 251, 0.28), inset 0 1px 0 rgba(255,255,255,0.4)' }}
          >
            <Plus strokeWidth={2.2} className="h-[13px] w-[13px]" />
            {t('rightbar.createCommunity')}
          </Link>
        </div>
      </Card>

      {/* Footer */}
      <div className="px-3 pt-1 text-[10.5px] leading-[1.6] text-[var(--color-text-dim)]">
        <div className="font-mono mt-1.5 text-[10px]">© 2026 Nexus Forum · v0.1.0</div>
      </div>

      <style>{`
        .live-dot {
          width: 5px; height: 5px; border-radius: 50%;
          background: var(--color-accent);
          box-shadow: 0 0 10px var(--color-accent-glow);
          animation: nexus-pulse 2s ease-in-out infinite;
          display: inline-block;
        }
      `}</style>
    </aside>
  );
}

function Card({ children }: { children: React.ReactNode }) {
  return (
    <div className="overflow-hidden rounded-[12px] border border-[var(--color-border)] bg-[var(--color-bg-1)]">
      {children}
    </div>
  );
}

function CardHead({ title, more }: { title: React.ReactNode; more?: string }) {
  const { t } = useTranslation();
  return (
    <div className="flex items-center justify-between px-4 pt-3.5 pb-2">
      <h3 className="m-0 inline-flex items-center gap-1.5 text-[12.5px] font-semibold tracking-tight text-[var(--color-text)]">
        {title}
      </h3>
      {more && (
        <Link to={more} className="inline-flex items-center gap-1 text-[11px] text-[var(--color-text-dim)] hover:text-[var(--color-accent)]">
          {t('rightbar.seeAll')}
          <ArrowRight className="h-3 w-3" />
        </Link>
      )}
    </div>
  );
}

function CommunityRow({ community, rank }: { community: Community; rank: number }) {
  const { t } = useTranslation();
  const [joined, setJoined] = useState(community.is_member);
  const [busy, setBusy] = useState(false);
  const isAuthed = useAppSelector((s) => s.auth.status === 'authenticated');
  const dispatch = useAppDispatch();

  async function toggle(e: React.MouseEvent) {
    e.preventDefault();
    if (!isAuthed || busy) return;
    setBusy(true);
    try {
      if (joined) {
        await leaveCommunity(community.slug);
        setJoined(false);
        dispatch(membershipsChanged());
      } else {
        await joinCommunity(community.slug);
        setJoined(true);
        dispatch(membershipsChanged());
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <Link
      to={`/c/${community.slug}`}
      className="flex items-center gap-2.5 border-t border-[var(--color-border)] px-4 py-2 text-[12.5px] transition hover:bg-[var(--color-surface)]"
    >
      <span className="font-mono w-3 text-[10.5px] text-[var(--color-text-dim)]">{rank}</span>
      <span
        className="grid h-6 w-6 place-items-center rounded-full border border-[var(--color-border)] text-[11px] font-semibold text-[var(--color-accent)]"
        style={{ background: 'linear-gradient(135deg, #2a3540, #1a2128)' }}
      >
        {community.slug[0]?.toUpperCase()}
      </span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-[13px] font-medium text-[var(--color-text)]">c/{community.slug}</div>
        <div className="font-mono text-[10.5px] text-[var(--color-text-dim)]">
          {formatCount(community.member_count)} {t('rightbar.members')}
        </div>
      </div>
      {community.is_banned ? (
        <Badge tone="danger">{t('community.banned')}</Badge>
      ) : (
      <button
        type="button"
        onClick={toggle}
        disabled={!isAuthed || busy}
        className={cn(
          'rounded-full border px-2.5 py-[3px] text-[11px] font-medium transition disabled:opacity-60',
          joined
            ? 'border-[var(--color-border)] bg-transparent text-[var(--color-text-muted)]'
            : 'border-[var(--color-border)] bg-[var(--color-bg-3)] text-[var(--color-text)] hover:border-[var(--color-accent)] hover:bg-[var(--color-accent)] hover:text-[#061218]',
        )}
      >
        {joined ? t('rightbar.joined') : t('rightbar.join')}
      </button>
      )}
    </Link>
  );
}

function formatCount(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, '') + 'k';
  return String(n);
}

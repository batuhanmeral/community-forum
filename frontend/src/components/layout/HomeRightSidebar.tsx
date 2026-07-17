import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { trendingCommunities, trendingPosts } from '@/api/trending';
import { joinCommunity, leaveCommunity } from '@/api/communities';
import type { Community } from '@/features/communities/types';
import type { Post } from '@/features/posts/types';
import { useAppSelector } from '@/app/hooks';
import { timeAgo } from '@/lib/time';
import { cn } from '@/lib/cn';

export function HomeRightSidebar() {
  const isAuthed = useAppSelector((s) => s.auth.status === 'authenticated');
  const [trendPosts, setTrendPosts] = useState<Post[]>([]);
  const [topComms, setTopComms] = useState<Community[]>([]);

  useEffect(() => {
    trendingPosts()
      .then((p) => setTrendPosts(p.slice(0, 5)))
      .catch(() => undefined);
    trendingCommunities()
      .then((c) => setTopComms(c.slice(0, 5)))
      .catch(() => undefined);
  }, []);

  return (
    <aside className="sticky top-[88px] hidden h-[calc(100vh-110px)] flex-col gap-4 overflow-y-auto pb-10 pt-6 lg:flex">
      {/* Promo card */}
      <div
        className="relative overflow-hidden rounded-[14px] border px-5 py-5"
        style={{
          borderColor: 'rgba(97, 218, 251, 0.18)',
          background: `radial-gradient(120% 80% at 0% 0%, rgba(97, 218, 251, 0.18), transparent 60%),
                       radial-gradient(80% 60% at 100% 100%, rgba(97, 218, 251, 0.08), transparent 60%),
                       linear-gradient(180deg, rgba(20,28,36,0.65), rgba(13,18,22,0.65))`,
          backdropFilter: 'blur(16px)',
        }}
      >
        <h4 className="font-serif-italic mb-1.5 text-[26px] leading-[1.05] tracking-tight">
          The forum,{' '}
          <em
            className="font-serif-italic text-[var(--color-accent)]"
            style={{ textShadow: '0 0 24px rgba(97, 218, 251, 0.4)' }}
          >
            rebuilt
          </em>
          .
        </h4>
        <p className="mb-3.5 text-[13px] leading-relaxed text-[var(--color-text-muted)]">
          Quiet, fast, no algorithm. Just the communities you joined and the threads worth your time.
        </p>
        <div className="mb-3.5 flex gap-3.5 border-t border-[var(--color-border)] pt-3">
          <Stat value="8.4M" label="Members" />
          <Stat value="142k" label="Online now" />
          <Stat value="∞" label="Algorithm" />
        </div>
        <Link
          to={isAuthed ? '/c/create' : '/register'}
          className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-[var(--color-accent)] px-4 py-2 text-[13.5px] font-semibold text-[#061218]"
          style={{ boxShadow: '0 4px 16px rgba(97, 218, 251, 0.28), inset 0 1px 0 rgba(255,255,255,0.4)' }}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" className="h-[15px] w-[15px]">
            <path d="M12 5v14m-7-7h14" />
          </svg>
          Create a community
        </Link>
      </div>

      {/* Trending */}
      <Card>
        <CardHead title={<><span className="live-dot" /> Trending now</>} more="/explore" />
        {trendPosts.length === 0 ? (
          <p className="px-[18px] py-3 text-[13px] text-[var(--color-text-muted)]">No trending posts yet.</p>
        ) : (
          trendPosts.map((p, i) => (
            <Link
              key={p.id}
              to={`/posts/${p.id}`}
              className="flex gap-3 border-t border-[var(--color-border)] px-[18px] py-[11px] text-[13px] transition hover:bg-[var(--color-surface)]"
            >
              <span className={cn('font-mono w-[18px] shrink-0 pt-0.5 text-[12px]', i < 3 ? 'text-[var(--color-accent)]' : 'text-[var(--color-text-dim)]')}>
                {String(i + 1).padStart(2, '0')}
              </span>
              <div className="min-w-0 flex-1">
                <div className="mb-0.5 text-[10.5px] uppercase tracking-[0.08em] text-[var(--color-text-dim)]">
                  c/{p.community} · Hot
                </div>
                <div className="line-clamp-2 text-[13.5px] font-medium leading-snug text-[var(--color-text)]">
                  {p.title}
                </div>
                <div className="font-mono mt-0.5 text-[11px] text-[var(--color-text-dim)]">
                  {p.score} points · {timeAgo(p.created_at)}
                </div>
              </div>
            </Link>
          ))
        )}
      </Card>

      {/* Top communities */}
      <Card>
        <CardHead title="Top communities" more="/c" />
        {topComms.length === 0 ? (
          <p className="px-[18px] py-3 text-[13px] text-[var(--color-text-muted)]">No active communities.</p>
        ) : (
          topComms.map((c, i) => <CommunityRow key={c.id} community={c} rank={i + 1} />)
        )}
      </Card>

      {/* Footer */}
      <Card>
        <div className="px-[18px] py-4 text-[11px] leading-[1.6] text-[var(--color-text-dim)]">
          <a href="#" className="mr-2 text-[var(--color-text-muted)] hover:text-[var(--color-accent)]">About</a>
          <a href="#" className="mr-2 text-[var(--color-text-muted)] hover:text-[var(--color-accent)]">Help</a>
          <a href="#" className="mr-2 text-[var(--color-text-muted)] hover:text-[var(--color-accent)]">Terms</a>
          <a href="#" className="mr-2 text-[var(--color-text-muted)] hover:text-[var(--color-accent)]">Privacy</a>
          <a href="#" className="mr-2 text-[var(--color-text-muted)] hover:text-[var(--color-accent)]">API</a>
          <div className="font-mono mt-2.5 text-[10.5px]">© 2026 Nexus Forum · v0.1.0</div>
        </div>
      </Card>

      <style>{`
        .live-dot {
          width: 6px; height: 6px; border-radius: 50%;
          background: var(--color-accent);
          box-shadow: 0 0 10px var(--color-accent-glow);
          animation: nexus-pulse 2s ease-in-out infinite;
          display: inline-block;
        }
      `}</style>
    </aside>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="flex-1">
      <div className="font-mono text-[18px] font-medium tracking-tight text-[var(--color-accent)]">{value}</div>
      <div className="mt-0.5 text-[10.5px] uppercase tracking-[0.08em] text-[var(--color-text-dim)]">{label}</div>
    </div>
  );
}

function Card({ children }: { children: React.ReactNode }) {
  return (
    <div className="overflow-hidden rounded-[14px] border border-[var(--color-border)] bg-[var(--color-bg-1)]">
      {children}
    </div>
  );
}

function CardHead({ title, more }: { title: React.ReactNode; more?: string }) {
  return (
    <div className="flex items-center justify-between px-[18px] pt-4 pb-2.5">
      <h3 className="m-0 inline-flex items-center gap-2 text-[13px] font-semibold tracking-tight text-[var(--color-text)]">
        {title}
      </h3>
      {more && (
        <Link to={more} className="text-[12px] text-[var(--color-text-dim)] hover:text-[var(--color-accent)]">
          See all →
        </Link>
      )}
    </div>
  );
}

function CommunityRow({ community, rank }: { community: Community; rank: number }) {
  const [joined, setJoined] = useState(community.is_member);
  const [busy, setBusy] = useState(false);
  const isAuthed = useAppSelector((s) => s.auth.status === 'authenticated');

  async function toggle(e: React.MouseEvent) {
    e.preventDefault();
    if (!isAuthed || busy) return;
    setBusy(true);
    try {
      if (joined) {
        await leaveCommunity(community.slug);
        setJoined(false);
      } else {
        await joinCommunity(community.slug);
        setJoined(true);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <Link
      to={`/c/${community.slug}`}
      className="flex items-center gap-3 border-t border-[var(--color-border)] px-[18px] py-2.5 text-[13px] transition hover:bg-[var(--color-surface)]"
    >
      <span className="font-mono w-3.5 text-[11px] text-[var(--color-text-dim)]">{rank}</span>
      <span
        className="grid h-7 w-7 place-items-center rounded-full border border-[var(--color-border)] text-[12px] font-semibold text-[var(--color-accent)]"
        style={{ background: 'linear-gradient(135deg, #2a3540, #1a2128)' }}
      >
        {community.slug[0]?.toUpperCase()}
      </span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-[13.5px] font-medium text-[var(--color-text)]">c/{community.slug}</div>
        <div className="font-mono text-[11.5px] text-[var(--color-text-dim)]">
          {formatCount(community.member_count)} members
        </div>
      </div>
      <button
        type="button"
        onClick={toggle}
        disabled={!isAuthed || busy}
        className={cn(
          'rounded-full border px-3 py-[5px] text-[11.5px] font-medium transition disabled:opacity-60',
          joined
            ? 'border-[var(--color-border)] bg-transparent text-[var(--color-text-muted)]'
            : 'border-[var(--color-border)] bg-[var(--color-bg-3)] text-[var(--color-text)] hover:border-[var(--color-accent)] hover:bg-[var(--color-accent)] hover:text-[#061218]',
        )}
      >
        {joined ? 'Joined' : 'Join'}
      </button>
    </Link>
  );
}

function formatCount(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, '') + 'k';
  return String(n);
}

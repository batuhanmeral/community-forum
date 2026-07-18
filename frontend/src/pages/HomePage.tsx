import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { listFeed, listFollowingFeed, type SortOption } from '@/api/posts';
import { listCommunities } from '@/api/communities';
import type { Post } from '@/features/posts/types';
import { useAppSelector } from '@/app/hooks';
import { Avatar } from '@/components/ui/Avatar';
import { PostCard } from '@/components/posts/PostCard';
import { cn } from '@/lib/cn';

interface SortTab {
  id: SortOption;
  label: string;
  icon: React.ReactNode;
}

const hotIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-[13px] w-[13px]">
    <path d="M13 3s4 4 4 9a5 5 0 0 1-10 0c0-2 1-3 2-4 0 0 0 2 2 2 0-4 2-7 2-7z" />
  </svg>
);
const newIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-[13px] w-[13px]">
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </svg>
);
const topIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-[13px] w-[13px]">
    <path d="M7 14l5-7 5 7M5 21h14" />
  </svg>
);

const SORT_TABS: SortTab[] = [
  { id: 'hot', label: 'Hot', icon: hotIcon },
  { id: 'new', label: 'New', icon: newIcon },
  { id: 'top', label: 'Top', icon: topIcon },
];

type FeedKind = 'home' | 'following';

type KindFilter = 'all' | 'text' | 'image' | 'link' | 'poll';

const KIND_FILTERS: Array<{ id: KindFilter; label: string }> = [
  { id: 'all', label: 'All posts' },
  { id: 'text', label: 'Discussion' },
  { id: 'image', label: 'Media' },
  { id: 'link', label: 'Links' },
  { id: 'poll', label: 'Polls' },
];

const NSFW_KEY = 'nexus.nsfwShown';

export function HomePage() {
  const user = useAppSelector((s) => s.auth.user);
  const isAuthed = useAppSelector((s) => s.auth.status === 'authenticated');
  const [posts, setPosts] = useState<Post[]>([]);
  const [memberCount, setMemberCount] = useState<number>(0);
  const [feedKind, setFeedKind] = useState<FeedKind>('home');
  const [sort, setSort] = useState<SortOption>('hot');
  const [kind, setKind] = useState<KindFilter>('all');
  const [nsfwShown, setNsfwShown] = useState<boolean>(() => localStorage.getItem(NSFW_KEY) === '1');
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);

  useEffect(() => {
    localStorage.setItem(NSFW_KEY, nsfwShown ? '1' : '0');
  }, [nsfwShown]);

  // Reset and load page 1 when filters change
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setPage(1);
    const fetcher = feedKind === 'following' ? listFollowingFeed : listFeed;
    fetcher({ sort, nsfw: nsfwShown ? 'show' : undefined, page: 1 })
      .then((d) => {
        if (cancelled) return;
        setPosts(d.results);
        setHasMore(Boolean(d.next));
      })
      .catch(() => undefined)
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [feedKind, sort, nsfwShown]);

  useEffect(() => {
    if (!isAuthed) {
      setMemberCount(0);
      return;
    }
    listCommunities({ ordering: '-member_count' })
      .then((d) => setMemberCount(d.results.filter((c) => c.is_member).length))
      .catch(() => undefined);
  }, [isAuthed]);

  const counts = useMemo(() => {
    const totals: Record<KindFilter, number> = { all: posts.length, text: 0, image: 0, link: 0, poll: 0 };
    for (const p of posts) totals[p.kind] = (totals[p.kind] ?? 0) + 1;
    return totals;
  }, [posts]);

  const filtered = useMemo(() => {
    if (kind === 'all') return posts;
    return posts.filter((p) => p.kind === kind);
  }, [posts, kind]);

  async function loadMore() {
    if (loadingMore || !hasMore) return;
    const next = page + 1;
    setLoadingMore(true);
    const fetcher = feedKind === 'following' ? listFollowingFeed : listFeed;
    try {
      const d = await fetcher({ sort, nsfw: nsfwShown ? 'show' : undefined, page: next });
      setPosts((p) => [...p, ...d.results]);
      setHasMore(Boolean(d.next));
      setPage(next);
    } finally {
      setLoadingMore(false);
    }
  }

  return (
    <div className="min-w-0">
      {/* Feed header */}
      <div className="mb-[18px] flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-baseline gap-2.5 text-[22px] font-semibold tracking-tight">
          <span>{feedKind === 'following' ? 'Following' : isAuthed ? 'Your feed' : 'Popular feed'}</span>
          <span className="font-mono text-[14px] font-normal text-[var(--color-text-dim)]">
            / {feedKind}
            {isAuthed && feedKind === 'home' && memberCount > 0
              ? ` · ${memberCount} ${memberCount === 1 ? 'community' : 'communities'}`
              : ''}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {isAuthed && (
            <div className="flex gap-0.5 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-1)] p-1">
              {(['home', 'following'] as FeedKind[]).map((k) => (
                <button
                  key={k}
                  type="button"
                  onClick={() => setFeedKind(k)}
                  className={cn(
                    'rounded-full px-3.5 py-1.5 text-[13px] font-medium capitalize transition',
                    feedKind === k
                      ? 'bg-[var(--color-bg-3)] text-[var(--color-text)] shadow-[0_1px_0_rgba(255,255,255,0.04),inset_0_1px_0_rgba(255,255,255,0.04)]'
                      : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]',
                  )}
                >
                  {k}
                </button>
              ))}
            </div>
          )}

          <div className="flex gap-0.5 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-1)] p-1">
            {SORT_TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setSort(t.id)}
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-[13px] font-medium transition',
                  sort === t.id
                    ? 'bg-[var(--color-bg-3)] text-[var(--color-text)] shadow-[0_1px_0_rgba(255,255,255,0.04),inset_0_1px_0_rgba(255,255,255,0.04)]'
                    : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]',
                )}
              >
                {t.icon}
                {t.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Filter pills + NSFW */}
      <div className="mb-3.5 flex items-center gap-1.5 overflow-x-auto pb-1">
        {KIND_FILTERS.map((f) => (
          <button
            key={f.id}
            type="button"
            onClick={() => setKind(f.id)}
            className={cn(
              'inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-3.5 py-[7px] text-[12.5px] font-normal transition',
              kind === f.id
                ? 'border-[rgba(97,218,251,0.3)] bg-[var(--color-accent-dim)] text-[var(--color-accent)]'
                : 'border-[var(--color-border)] bg-[var(--color-bg-1)] text-[var(--color-text-muted)] hover:bg-[var(--color-bg-elevated)] hover:text-[var(--color-text)]',
            )}
          >
            {f.label}
            <span className="font-mono text-[11px] opacity-80">{counts[f.id]}</span>
          </button>
        ))}

        <div className="ml-auto pr-1">
          <button
            type="button"
            onClick={() => setNsfwShown((v) => !v)}
            title={nsfwShown ? 'Hide NSFW' : 'Show NSFW'}
            className={cn(
              'inline-flex items-center gap-2 whitespace-nowrap rounded-full border px-3 py-[7px] text-[12px] font-medium transition',
              nsfwShown
                ? 'border-[rgba(255,106,138,0.3)] bg-[rgba(255,106,138,0.08)] text-[var(--color-danger)]'
                : 'border-[var(--color-border)] bg-[var(--color-bg-1)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]',
            )}
          >
            <span
              className={cn(
                'relative inline-block h-3 w-5 rounded-full transition-colors',
                nsfwShown ? 'bg-[var(--color-danger)]' : 'bg-[var(--color-bg-3)]',
              )}
            >
              <span
                className={cn(
                  'absolute top-0.5 h-2 w-2 rounded-full bg-white transition-all',
                  nsfwShown ? 'left-2.5' : 'left-0.5',
                )}
              />
            </span>
            NSFW
          </button>
        </div>
      </div>

      {/* Compose */}
      {isAuthed && (
        <Link
          to="/submit"
          className="mb-[18px] flex items-center gap-3 rounded-[14px] border border-[var(--color-border)] bg-[var(--color-bg-1)] px-3.5 py-3 transition hover:border-[var(--color-border-strong)]"
        >
          <Avatar src={user?.avatar} alt={user?.username} size="md" />
          <div className="flex-1 cursor-text rounded-[10px] border border-transparent bg-[var(--color-bg-elevated)] px-2.5 py-2 text-[14px] text-[var(--color-text-muted)] transition hover:border-[var(--color-border)] hover:bg-[var(--color-bg-3)]">
            What's on your mind{user ? `, ${user.username}` : ''}?
          </div>
          <div className="flex gap-1">
            <ComposeTool title="Image">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className="h-[17px] w-[17px]">
                <rect x="3" y="5" width="18" height="14" rx="2" />
                <circle cx="9" cy="10" r="1.5" />
                <path d="M21 16l-5-5-9 8" />
              </svg>
            </ComposeTool>
            <ComposeTool title="Link">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className="h-[17px] w-[17px]">
                <path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7L11 7M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7L13 17" />
              </svg>
            </ComposeTool>
            <ComposeTool title="Poll">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className="h-[17px] w-[17px]">
                <rect x="3" y="11" width="4" height="9" rx="1" />
                <rect x="10" y="6" width="4" height="14" rx="1" />
                <rect x="17" y="13" width="4" height="7" rx="1" />
              </svg>
            </ComposeTool>
          </div>
        </Link>
      )}

      {/* Posts */}
      {loading ? (
        <div className="flex flex-col gap-3.5">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-32 animate-pulse rounded-[14px] border border-[var(--color-border)] bg-[var(--color-bg-1)]" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-[14px] border border-[var(--color-border)] bg-[var(--color-bg-1)] px-5 py-16 text-center text-[13px] text-[var(--color-text-dim)]">
          {kind === 'all' ? (
            feedKind === 'following' ? (
              <>
                You aren't following anyone yet.{' '}
                <Link to="/explore" className="text-[var(--color-accent)] hover:underline">
                  Discover users →
                </Link>
              </>
            ) : isAuthed ? (
              <>
                Your feed is empty.{' '}
                <Link to="/c" className="text-[var(--color-accent)] hover:underline">
                  Browse communities →
                </Link>
              </>
            ) : (
              'No posts yet. Be the first to contribute!'
            )
          ) : (
            'No posts match this filter.'
          )}
        </div>
      ) : (
        filtered.map((p) => <PostCard key={p.id} post={p} />)
      )}

      {filtered.length > 0 && hasMore && (
        <div className="py-6 text-center text-[13px] text-[var(--color-text-dim)]">
          <button
            type="button"
            onClick={loadMore}
            disabled={loadingMore}
            className="inline-flex items-center gap-1.5 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-4 py-2 text-[13px] font-medium text-[var(--color-text-soft)] transition hover:bg-[var(--color-bg-3)] hover:text-[var(--color-text)] disabled:opacity-60"
          >
            {loadingMore ? 'Loading…' : 'Load more posts'}
          </button>
        </div>
      )}
    </div>
  );
}

function ComposeTool({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <button
      type="button"
      title={title}
      onClick={(e) => e.preventDefault()}
      className="grid h-9 w-9 place-items-center rounded-[10px] text-[var(--color-text-muted)] transition hover:bg-[var(--color-bg-3)] hover:text-[var(--color-accent)]"
    >
      {children}
    </button>
  );
}

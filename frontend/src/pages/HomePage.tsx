import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { listFeed, listFollowingFeed, type SortOption, type TimeWindow } from '@/api/posts';
import { listCommunities } from '@/api/communities';
import { updatePreferences } from '@/api/users';
import type { Post } from '@/features/posts/types';
import { setUser } from '@/features/auth/authSlice';
import { useAppDispatch, useAppSelector } from '@/app/hooks';
import { Avatar } from '@/components/ui/Avatar';
import { PageTitle } from '@/components/ui/PageTitle';
import { PostCard } from '@/components/posts/PostCard';
import { TimeRangeSelect } from '@/components/posts/TimeRangeSelect';
import { cn } from '@/lib/cn';
import { ArrowRight, ArrowUpToLine, BarChart3, Clock, Flame, Image as ImageIcon, Link as LinkIcon } from 'lucide-react';

interface SortTab {
  id: SortOption;
  icon: React.ReactNode;
}

const hotIcon = (
  <Flame className="h-[13px] w-[13px]" />
);
const newIcon = (
  <Clock className="h-[13px] w-[13px]" />
);
const topIcon = (
  <ArrowUpToLine className="h-[13px] w-[13px]" />
);

const SORT_TABS: SortTab[] = [
  { id: 'hot', icon: hotIcon },
  { id: 'new', icon: newIcon },
  { id: 'top', icon: topIcon },
];

type FeedKind = 'home' | 'following';

type KindFilter = 'all' | 'text' | 'image' | 'link' | 'poll';

const KIND_FILTERS: KindFilter[] = ['all', 'text', 'image', 'link', 'poll'];

export type FeedVariant = 'home' | 'popular' | 'all';

const VARIANT_DEFAULT_SORT: Record<FeedVariant, SortOption> = {
  home: 'hot',
  popular: 'top',
  all: 'new',
};

export function HomePage({ variant = 'home' }: { variant?: FeedVariant }) {
  const { t } = useTranslation();
  const user = useAppSelector((s) => s.auth.user);
  const isAuthed = useAppSelector((s) => s.auth.status === 'authenticated');
  const dispatch = useAppDispatch();
  const [posts, setPosts] = useState<Post[]>([]);
  const [memberCount, setMemberCount] = useState<number>(0);
  const [feedKind, setFeedKind] = useState<FeedKind>('home');
  const [sort, setSort] = useState<SortOption>(VARIANT_DEFAULT_SORT[variant]);
  const [timeRange, setTimeRange] = useState<TimeWindow>('all');

  // Reset feed state when navigating between /, /popular and /all
  useEffect(() => {
    setSort(VARIANT_DEFAULT_SORT[variant]);
    setTimeRange('all');
    setFeedKind('home');
  }, [variant]);
  const [kind, setKind] = useState<KindFilter>('all');
  const [nsfwBusy, setNsfwBusy] = useState(false);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);

  // Server-stored preference; anon users never see NSFW (enforced server-side).
  const nsfwShown = user?.show_nsfw ?? false;

  async function toggleNsfw() {
    if (!user || nsfwBusy) return;
    setNsfwBusy(true);
    try {
      const updated = await updatePreferences({ show_nsfw: !nsfwShown });
      dispatch(setUser(updated));
    } finally {
      setNsfwBusy(false);
    }
  }

  // Reset and load page 1 when filters change
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setPage(1);
    const fetcher = feedKind === 'following' ? listFollowingFeed : listFeed;
    fetcher({
      sort,
      t: timeRange,
      nsfw: isAuthed ? (nsfwShown ? 'show' : 'hide') : undefined,
      page: 1,
      scope: variant !== 'home' ? 'all' : undefined,
    })
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
  }, [feedKind, sort, timeRange, nsfwShown, variant, isAuthed]);

  useEffect(() => {
    if (!isAuthed) {
      setMemberCount(0);
      return;
    }
    // Only the total is needed, so ask the server to count joined communities.
    listCommunities({ joined: true, page_size: 1 })
      .then((d) => setMemberCount(d.count))
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
      const d = await fetcher({
        sort,
        t: timeRange,
        nsfw: isAuthed ? (nsfwShown ? 'show' : 'hide') : undefined,
        page: next,
        scope: variant !== 'home' ? 'all' : undefined,
      });
      setPosts((p) => [...p, ...d.results]);
      setHasMore(Boolean(d.next));
      setPage(next);
    } finally {
      setLoadingMore(false);
    }
  }

  const headerTitle =
    variant === 'popular'
      ? t('feed.title_popular')
      : variant === 'all'
        ? t('feed.title_all')
        : feedKind === 'following'
          ? t('feed.title_following')
          : isAuthed
            ? t('feed.title_home')
            : t('feed.title_anon');
  // The plain home feed keeps the bare app name as its title.
  const pageTitle = variant === 'popular' ? t('feed.title_popular') : variant === 'all' ? t('feed.title_all') : undefined;

  return (
    <div className="min-w-0">
      <PageTitle title={pageTitle} />
      {/* Feed header */}
      <div className="mb-[18px] flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <div className="flex items-baseline gap-2.5 text-[22px] font-semibold tracking-tight">
            <span>{headerTitle}</span>
            {isAuthed && variant === 'home' && feedKind === 'home' && memberCount > 0 && (
              <span className="text-[14px] font-normal text-[var(--color-text-dim)]">
                {t('feed.communityCount', { count: memberCount })}
              </span>
            )}
          </div>
          {isAuthed && variant === 'home' && (
            <div className="flex gap-0.5 rounded-[var(--radius-control)] border border-[var(--color-border)] bg-[var(--color-bg-1)] p-1">
              {(['home', 'following'] as FeedKind[]).map((k) => (
                <button
                  key={k}
                  type="button"
                  onClick={() => setFeedKind(k)}
                  className={cn(
                    'rounded-[var(--radius-control-inner)] px-3.5 py-1.5 text-[13px] font-medium transition',
                    feedKind === k
                      ? 'bg-[var(--color-bg-3)] text-[var(--color-text)]'
                      : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]',
                  )}
                >
                  {t(`feed.tab_${k}`)}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <TimeRangeSelect value={timeRange} onChange={setTimeRange} />

          <div className="flex gap-0.5 rounded-[var(--radius-control)] border border-[var(--color-border)] bg-[var(--color-bg-1)] p-1">
            {SORT_TABS.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setSort(tab.id)}
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-[var(--radius-control-inner)] px-3.5 py-1.5 text-[13px] font-medium transition',
                  sort === tab.id
                    ? 'bg-[var(--color-bg-3)] text-[var(--color-text)]'
                    : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]',
                )}
              >
                {tab.icon}
                {t(`sort.${tab.id}`)}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Filter pills + NSFW */}
      <div className="mb-3.5 flex items-center gap-1.5 overflow-x-auto pb-1">
        {KIND_FILTERS.map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setKind(f)}
            className={cn(
              'inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-3.5 py-[7px] text-[12.5px] font-normal transition',
              kind === f
                ? 'border-[var(--color-link)]/30 bg-[var(--color-link-dim)] text-[var(--color-link)]'
                : 'border-[var(--color-border)] bg-[var(--color-bg-1)] text-[var(--color-text-muted)] hover:bg-[var(--color-bg-elevated)] hover:text-[var(--color-text)]',
            )}
          >
            {t(`feed.kind_${f}`)}
            <span className="font-mono text-[11px] opacity-80">{counts[f]}</span>
          </button>
        ))}

        <div className="ml-auto pr-1">
          {isAuthed && (
          <button
            type="button"
            onClick={toggleNsfw}
            disabled={nsfwBusy}
            title={nsfwShown ? t('feed.nsfwHide') : t('feed.nsfwShow')}
            className={cn(
              'inline-flex items-center gap-2 whitespace-nowrap rounded-full border px-3 py-[7px] text-[12px] font-medium transition',
              nsfwShown
                ? 'border-[var(--color-danger)]/30 bg-[var(--color-danger-dim)] text-[var(--color-danger)]'
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
                  'absolute top-0.5 h-2 w-2 rounded-full bg-[var(--color-text)] transition-all',
                  nsfwShown ? 'left-2.5' : 'left-0.5',
                )}
              />
            </span>
            {t('post.nsfw')}
          </button>
          )}
        </div>
      </div>

      {/* Compose */}
      {isAuthed && (
        <div className="relative mb-[18px] flex items-center gap-3 rounded-[14px] border border-[var(--color-border)] bg-[var(--color-bg-1)] px-3.5 py-3 transition hover:border-[var(--color-border-strong)]">
          <Avatar src={user?.avatar} alt={user?.username} size="md" />
          <div className="flex-1 cursor-text rounded-[10px] border border-transparent bg-[var(--color-bg-elevated)] px-2.5 py-2 text-[14px] text-[var(--color-text-muted)] transition hover:border-[var(--color-border)] hover:bg-[var(--color-bg-3)]">
            {/* The ::after overlay makes the whole box clickable without nesting links */}
            <Link
              to="/submit"
              className="outline-none after:absolute after:inset-0 after:rounded-[14px] focus-visible:after:ring-2 focus-visible:after:ring-[var(--color-link)]"
            >
              {user ? t('feed.composePromptNamed', { name: user.username }) : t('feed.composePrompt')}
            </Link>
          </div>
          <div className="relative z-10 flex gap-1">
            <ComposeTool title={t('post.kind_image')} kind="image">
              <ImageIcon className="h-[17px] w-[17px]" />
            </ComposeTool>
            <ComposeTool title={t('post.kind_link')} kind="link">
              <LinkIcon className="h-[17px] w-[17px]" />
            </ComposeTool>
            <ComposeTool title={t('post.kind_poll')} kind="poll">
              <BarChart3 className="h-[17px] w-[17px]" />
            </ComposeTool>
          </div>
        </div>
      )}

      {/* Posts */}
      {loading ? (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-28 animate-pulse rounded-[var(--radius-card)] border border-[var(--color-border-strong)] bg-[var(--color-bg-1)]" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-[14px] border border-[var(--color-border)] bg-[var(--color-bg-1)] px-5 py-16 text-center text-[13px] text-[var(--color-text-dim)]">
          {kind === 'all' ? (
            feedKind === 'following' ? (
              <>
                {t('feed.followingEmpty')}{' '}
                <Link to="/search?type=user" className="inline-flex items-center gap-1 text-[var(--color-link)] underline underline-offset-2 hover:text-[var(--color-link-hover)]">
                  {t('feed.discoverUsers')}
                  <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </>
            ) : isAuthed ? (
              <>
                {t('feed.feedEmpty')}{' '}
                <Link to="/c" className="inline-flex items-center gap-1 text-[var(--color-link)] underline underline-offset-2 hover:text-[var(--color-link-hover)]">
                  {t('composer.browseCommunities')}
                  <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </>
            ) : (
              t('feed.anonEmpty')
            )
          ) : (
            t('feed.filterEmpty')
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
            {loadingMore ? t('common.loading') : t('community.loadMore')}
          </button>
        </div>
      )}
    </div>
  );
}

function ComposeTool({ title, kind, children }: { title: string; kind: string; children: React.ReactNode }) {
  return (
    <Link
      to={`/submit?kind=${kind}`}
      title={title}
      className="grid h-9 w-9 place-items-center rounded-[10px] text-[var(--color-text-muted)] transition hover:bg-[var(--color-bg-3)] hover:text-[var(--color-link)]"
    >
      {children}
    </Link>
  );
}

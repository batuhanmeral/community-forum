import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { listFeed, listFollowingFeed, type SortOption, type TimeWindow } from '@/api/posts';
import { updatePreferences } from '@/api/users';
import type { Post } from '@/features/posts/types';
import { setUser } from '@/features/auth/authSlice';
import { useAppDispatch, useAppSelector } from '@/app/hooks';
import { PageTitle } from '@/components/ui/PageTitle';
import { PostCard } from '@/components/posts/PostCard';
import { TimeRangeSelect } from '@/components/posts/TimeRangeSelect';
import { PostSortTabs } from '@/components/posts/PostSortTabs';
import { CreatePostLink } from '@/components/posts/CreatePostLink';
import { cn } from '@/lib/cn';
import { ArrowRight } from 'lucide-react';

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
      <h1 className="sr-only">{headerTitle}</h1>
      <div className="mb-[18px] flex flex-wrap items-center gap-2">
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
        <div className="ml-auto flex flex-wrap items-center justify-end gap-2 max-sm:gap-1.5">
          <PostSortTabs value={sort} onChange={setSort} />
          <TimeRangeSelect value={timeRange} onChange={setTimeRange} iconOnly />
          {isAuthed && <CreatePostLink to="/submit" />}
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
              'inline-flex items-center gap-1.5 whitespace-nowrap rounded-[var(--radius-control)] border px-3.5 py-[7px] text-[12.5px] font-normal transition',
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
              'inline-flex items-center gap-2 whitespace-nowrap rounded-[var(--radius-control)] border px-3 py-[7px] text-[12px] font-medium transition',
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
            className="inline-flex items-center gap-1.5 rounded-[var(--radius-control)] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-4 py-2 text-[13px] font-medium text-[var(--color-text-soft)] transition hover:bg-[var(--color-bg-3)] hover:text-[var(--color-text)] disabled:opacity-60"
          >
            {loadingMore ? t('common.loading') : t('community.loadMore')}
          </button>
        </div>
      )}
    </div>
  );
}

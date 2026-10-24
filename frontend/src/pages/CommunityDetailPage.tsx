import { useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  getCommunity,
  joinCommunity,
  leaveCommunity,
  listRules,
  updateNotifyLevel,
} from '@/api/communities';
import { listCommunityPosts, type SortOption, type TimeWindow } from '@/api/posts';
import type {
  Community,
  CommunityRule,
  NotifyLevel,
} from '@/features/communities/types';
import type { Post } from '@/features/posts/types';
import { membershipsChanged } from '@/features/communities/membershipsSlice';
import { useAppDispatch, useAppSelector } from '@/app/hooks';
import { Avatar } from '@/components/ui/Avatar';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { PageTitle } from '@/components/ui/PageTitle';
import { PostCard } from '@/components/posts/PostCard';
import { PostSortTabs } from '@/components/posts/PostSortTabs';
import { TimeRangeSelect } from '@/components/posts/TimeRangeSelect';
import { CreatePostLink } from '@/components/posts/CreatePostLink';
import { cn } from '@/lib/cn';
import { ArrowLeft, Bell, BellOff, ShieldCheck } from 'lucide-react';

export function CommunityDetailPage() {
  const { t } = useTranslation();
  const { slug = '' } = useParams<{ slug: string }>();
  const isAuthed = useAppSelector((s) => s.auth.status === 'authenticated');
  const dispatch = useAppDispatch();

  const [community, setCommunity] = useState<Community | null>(null);
  const [rules, setRules] = useState<CommunityRule[]>([]);
  const [posts, setPosts] = useState<Post[]>([]);
  const [postsLoading, setPostsLoading] = useState(true);
  const [sort, setSort] = useState<SortOption>('hot');
  const [timeRange, setTimeRange] = useState<TimeWindow>('all');
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [notifyLevel, setNotifyLevel] = useState<NotifyLevel>('all');
  const [actionLoading, setActionLoading] = useState(false);
  const [nextPage, setNextPage] = useState<number | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [loadMoreFailed, setLoadMoreFailed] = useState(false);
  // Bumped on every (re)fetch and unmount so late load-more responses can be discarded.
  const listVersion = useRef(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setNotFound(false);
    Promise.all([getCommunity(slug), listRules(slug).catch(() => [])])
      .then(([c, r]) => {
        if (cancelled) return;
        setCommunity(c);
        setNotifyLevel(c.my_notify_level ?? 'all');
        setRules(r);
      })
      .catch(() => {
        if (!cancelled) setNotFound(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [slug]);

  useEffect(() => {
    if (!slug) return;
    let cancelled = false;
    listVersion.current++;
    setPostsLoading(true);
    setNextPage(null);
    setLoadMoreFailed(false);
    setLoadingMore(false);
    listCommunityPosts(slug, { sort, t: timeRange })
      .then((d) => {
        if (cancelled) return;
        setPosts(d.results);
        setNextPage(d.next ? 2 : null);
      })
      .catch(() => undefined)
      .finally(() => {
        if (!cancelled) setPostsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [slug, sort, timeRange]);

  useEffect(
    () => () => {
      listVersion.current = -1;
    },
    [],
  );

  async function loadMorePosts() {
    if (nextPage === null) return;
    const version = listVersion.current;
    setLoadingMore(true);
    setLoadMoreFailed(false);
    try {
      const d = await listCommunityPosts(slug, { sort, t: timeRange, page: nextPage });
      if (version !== listVersion.current) return;
      setPosts((ps) => [...ps, ...d.results.filter((p) => !ps.some((x) => x.id === p.id))]);
      setNextPage(d.next ? nextPage + 1 : null);
    } catch {
      if (version === listVersion.current) setLoadMoreFailed(true);
    } finally {
      if (version === listVersion.current) setLoadingMore(false);
    }
  }

  async function handleJoinLeave() {
    if (!community) return;
    setActionLoading(true);
    try {
      if (community.is_member) {
        await leaveCommunity(community.slug);
        setCommunity({
          ...community,
          is_member: false,
          my_role: null,
          member_count: Math.max(0, community.member_count - 1),
        });
        dispatch(membershipsChanged());
      } else {
        await joinCommunity(community.slug);
        setCommunity({
          ...community,
          is_member: true,
          my_role: 'member',
          member_count: community.member_count + 1,
        });
        setNotifyLevel('all');
        dispatch(membershipsChanged());
      }
    } finally {
      setActionLoading(false);
    }
  }

  async function handleNotifyChange(level: NotifyLevel) {
    if (!community) return;
    const prev = notifyLevel;
    setNotifyLevel(level);
    try {
      await updateNotifyLevel(community.slug, level);
    } catch {
      setNotifyLevel(prev);
    }
  }

  if (loading) {
    return (
      <>
        <PageTitle />
        <div className="text-sm text-[var(--color-text-muted)]">{t('common.loading')}</div>
      </>
    );
  }
  if (notFound || !community) {
    return (
      <Card>
        <PageTitle title={t('communityPage.notFound')} />
        <h2 className="text-lg font-semibold">{t('communityPage.notFound')}</h2>
        <p className="mt-1 text-sm text-[var(--color-text-muted)]">
          {t('communityPage.notFoundBody', { slug })}
        </p>
        <Link to="/c" className="mt-3 inline-flex items-center gap-1 text-sm text-[var(--color-link)] hover:underline">
          <ArrowLeft className="h-3.5 w-3.5" />
          {t('composer.browseCommunities')}
        </Link>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <PageTitle title={`c/${community.slug}`} />
      <Card padded={false} className="overflow-hidden">
        <div className="h-24 w-full bg-[var(--color-bg-3)]" />
        <div className="px-5 py-4">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="flex min-w-0 items-start gap-4">
              <div className="-mt-12">
                <Avatar
                  src={community.avatar}
                  alt={community.name}
                  size="lg"
                  className="ring-4 ring-[var(--color-surface)]"
                />
              </div>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h1 className="text-xl font-bold tracking-tight">{community.name}</h1>
                  {community.is_nsfw && <Badge tone="danger">{t('post.nsfw')}</Badge>}
                </div>
                <p className="text-sm text-[var(--color-text-muted)]">c/{community.slug}</p>
                <p className="mt-0.5 text-xs text-[var(--color-text-dim)]">
                  {t('rightbar.members', {
                    count: community.member_count,
                    formatted: community.member_count.toLocaleString(),
                  })}
                </p>
              </div>
            </div>

            {isAuthed && (
              <div className="flex items-center gap-2 self-start">
                {(community.my_role === 'admin' || community.my_role === 'moderator') && (
                  <Link to={`/c/${community.slug}/mod`}>
                    <Button variant="secondary" size="md">
                      <ShieldCheck className="h-4 w-4" />
                      {t('communityPage.modTools')}
                    </Button>
                  </Link>
                )}
                {community.is_member && (
                  <NotifyDropdown value={notifyLevel} onChange={handleNotifyChange} />
                )}
                {community.is_banned ? (
                  <Badge tone="danger">{t('community.banned')}</Badge>
                ) : (
                  <Button
                    variant={community.is_member ? 'secondary' : 'primary'}
                    onClick={handleJoinLeave}
                    loading={actionLoading}
                  >
                    {community.is_member ? t('rightbar.joined') : t('rightbar.join')}
                  </Button>
                )}
              </div>
            )}
          </div>
          {community.description && (
            <p className="mt-3 text-sm text-[var(--color-text-muted)] whitespace-pre-wrap">
              {community.description}
            </p>
          )}
        </div>
      </Card>

      <div className="flex flex-col gap-3">
        {rules.length > 0 && (
          <Card>
            <h2 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
              {t('communityPage.rules')}
            </h2>
            <ol className="mt-3 grid gap-1.5 text-sm sm:grid-cols-2">
              {rules.map((r, i) => (
                <li key={r.id} className="flex gap-2">
                  <span className="text-[var(--color-text-dim)]">{i + 1}.</span>
                  <span>{r.short}</span>
                </li>
              ))}
            </ol>
          </Card>
        )}

        <div className="flex flex-wrap items-center gap-2">
          {isAuthed && <CreatePostLink to={`/c/${community.slug}/submit`} showLabel />}
          <div className="ml-auto flex items-center gap-2 max-sm:gap-1.5">
            <PostSortTabs value={sort} onChange={setSort} />
            <TimeRangeSelect value={timeRange} onChange={setTimeRange} iconOnly />
          </div>
        </div>

        {postsLoading ? (
          <div className="flex flex-col gap-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Card key={i} className="h-28 animate-pulse" />
            ))}
          </div>
        ) : posts.length === 0 ? (
          <Card>
            <p className="text-sm text-[var(--color-text-muted)]">
              {t('communityPage.noPosts')}
            </p>
          </Card>
        ) : (
          posts.map((p) => <PostCard key={p.id} post={p} hideCommunity />)
        )}
        {!postsLoading && nextPage !== null && (
          <Button variant="secondary" onClick={loadMorePosts} loading={loadingMore}>
            {t('community.loadMore')}
          </Button>
        )}
        {loadMoreFailed && (
          <p role="alert" className="text-sm text-[var(--color-danger)]">
            {t('community.loadMoreFailed')}
          </p>
        )}
      </div>
    </div>
  );
}

interface NotifyDropdownProps {
  value: NotifyLevel;
  onChange: (level: NotifyLevel) => void;
}

function NotifyDropdown({ value, onChange }: NotifyDropdownProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const label = `${t('communityPage.notifyLevel')}: ${t(`communityPage.notify_${value}`)}`;

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="grid h-10 w-10 place-items-center rounded-[var(--radius-control)] border border-[var(--color-border)] bg-[var(--color-surface)] transition-colors hover:bg-[var(--color-surface-hover)]"
        aria-expanded={open}
        aria-label={label}
        title={label}
      >
        {value === 'off' ? <BellOff className="h-4 w-4" /> : <Bell className="h-4 w-4" />}
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-48 overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] shadow-md">
          {(['all', 'posts_only', 'off'] as NotifyLevel[]).map((level) => (
            <button
              key={level}
              type="button"
              onClick={() => {
                onChange(level);
                setOpen(false);
              }}
              className={cn(
                'block w-full px-4 py-2.5 text-left text-sm hover:bg-[var(--color-surface-hover)]',
                level === value && 'text-[var(--color-link)]',
              )}
            >
              {t(`communityPage.notify_${level}`)}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

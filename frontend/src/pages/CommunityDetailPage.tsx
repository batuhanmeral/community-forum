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
import { listCommunityPosts, type SortOption } from '@/api/posts';
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
import { PostCard } from '@/components/posts/PostCard';
import { PostSortTabs } from '@/components/posts/PostSortTabs';
import { cn } from '@/lib/cn';

const notifyLabels: Record<NotifyLevel, string> = {
  all: 'All updates',
  posts_only: 'Posts only',
  off: 'Muted',
};

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
    listCommunityPosts(slug, { sort })
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
  }, [slug, sort]);

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
      const d = await listCommunityPosts(slug, { sort, page: nextPage });
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
    return <div className="text-sm text-[var(--color-text-muted)]">Loading…</div>;
  }
  if (notFound || !community) {
    return (
      <Card>
        <h2 className="text-lg font-semibold">Community not found</h2>
        <p className="mt-1 text-sm text-[var(--color-text-muted)]">
          The community c/{slug} doesn't exist.
        </p>
        <Link to="/c" className="mt-3 inline-block text-sm text-[var(--color-accent)] hover:underline">
          ← Browse communities
        </Link>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <Card padded={false} className="overflow-hidden">
        <div className="h-24 w-full bg-gradient-to-r from-[var(--color-accent)]/30 via-[var(--color-surface-hover)] to-[var(--color-surface)]" />
        <div className="flex flex-col gap-4 px-5 py-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-4">
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
                {community.is_nsfw && <Badge tone="danger">NSFW</Badge>}
              </div>
              <p className="text-sm text-[var(--color-text-muted)]">c/{community.slug}</p>
              <p className="mt-0.5 text-xs text-[var(--color-text-dim)]">
                {community.member_count.toLocaleString()} member
                {community.member_count === 1 ? '' : 's'}
              </p>
            </div>
          </div>

          {isAuthed && (
            <div className="flex items-center gap-2 self-start">
              {(community.my_role === 'admin' || community.my_role === 'moderator') && (
                <Link to={`/c/${community.slug}/mod`}>
                  <Button variant="secondary" size="md">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4">
                      <path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z" />
                    </svg>
                    Mod tools
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
                  {community.is_member ? 'Joined' : 'Join'}
                </Button>
              )}
            </div>
          )}
        </div>
      </Card>

      <div className="flex flex-col gap-3">
        {community.description && (
          <Card>
            <p className="text-sm text-[var(--color-text-muted)] whitespace-pre-wrap">
              {community.description}
            </p>
          </Card>
        )}

        {rules.length > 0 && (
          <Card>
            <h2 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
              Community rules
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

        <div className="flex items-center justify-between gap-2">
          <PostSortTabs value={sort} onChange={setSort} />
          {isAuthed && (
            <Link to={`/c/${community.slug}/submit`}>
              <Button variant="primary" size="sm">
                Create post
              </Button>
            </Link>
          )}
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
              No posts in this community yet.
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
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

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
        className="inline-flex h-10 items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-3 text-sm transition-colors hover:bg-[var(--color-surface-hover)]"
        aria-label="Notification level"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4">
          <path d="M6 8a6 6 0 1 1 12 0v4l1.5 3h-15L6 12V8Z" />
          <path d="M10 19a2 2 0 0 0 4 0" />
        </svg>
        <span className="hidden sm:inline">{notifyLabels[value]}</span>
        <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4 text-[var(--color-text-muted)]">
          <path d="M5.23 7.21a.75.75 0 0 1 1.06.02L10 11.06l3.71-3.83a.75.75 0 1 1 1.08 1.04l-4.25 4.39a.75.75 0 0 1-1.08 0L5.21 8.27a.75.75 0 0 1 .02-1.06Z" />
        </svg>
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-48 overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] shadow-2xl">
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
                level === value && 'text-[var(--color-accent)]',
              )}
            >
              {notifyLabels[level]}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

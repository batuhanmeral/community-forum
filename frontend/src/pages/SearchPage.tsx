import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useSearchParams } from 'react-router-dom';
import { search, type SearchType } from '@/api/search';
import type { Community } from '@/features/communities/types';
import type { Post } from '@/features/posts/types';
import type { UserProfile } from '@/api/users';
import { Card } from '@/components/ui/Card';
import { Avatar } from '@/components/ui/Avatar';
import { PostCard } from '@/components/posts/PostCard';
import { FollowButton } from '@/components/follow/FollowButton';
import { cn } from '@/lib/cn';

const TABS: { type: SearchType; label: string }[] = [
  { type: 'post', label: 'search.posts' },
  { type: 'community', label: 'search.communities' },
  { type: 'user', label: 'search.people' },
];

function isType(v: string | null): v is SearchType {
  return v === 'post' || v === 'community' || v === 'user';
}

export function SearchPage() {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const q = params.get('q')?.trim() ?? '';
  const typeParam = params.get('type');
  const type: SearchType = isType(typeParam) ? typeParam : 'post';

  const [results, setResults] = useState<(Post | Community | UserProfile)[]>([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);

  useEffect(() => {
    if (!q) {
      setResults([]);
      setCount(0);
      setHasMore(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setPage(1);
    search(type, q, 1)
      .then((d) => {
        if (cancelled) return;
        setResults(d.results);
        setCount(d.count);
        setHasMore(Boolean(d.next));
      })
      .catch(() => {
        if (!cancelled) {
          setResults([]);
          setCount(0);
          setHasMore(false);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [q, type]);

  async function loadMore() {
    if (loadingMore || !hasMore) return;
    const next = page + 1;
    setLoadingMore(true);
    try {
      const d = await search(type, q, next);
      setResults((arr) => [...arr, ...d.results]);
      setHasMore(Boolean(d.next));
      setPage(next);
    } finally {
      setLoadingMore(false);
    }
  }

  function selectTab(t: SearchType) {
    setParams({ q, type: t }, { replace: true });
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-[22px] font-semibold tracking-tight">
          {q ? (
            <>
              {t('search.resultsFor')}{' '}
              <span className="text-[var(--color-accent)]">“{q}”</span>
            </>
          ) : (
            t('search.title')
          )}
        </h1>
        {q && (
          <p className="font-mono text-[12px] text-[var(--color-text-dim)]">
            {count.toLocaleString()} {t('search.found')}
          </p>
        )}
      </div>

      <div className="flex gap-0.5 self-start rounded-full border border-[var(--color-border)] bg-[var(--color-bg-1)] p-1">
        {TABS.map((tab) => (
          <button
            key={tab.type}
            type="button"
            onClick={() => selectTab(tab.type)}
            className={cn(
              'rounded-full px-4 py-1.5 text-[13px] font-medium transition',
              type === tab.type
                ? 'bg-[var(--color-bg-3)] text-[var(--color-text)] shadow-[0_1px_0_rgba(255,255,255,0.04),inset_0_1px_0_rgba(255,255,255,0.04)]'
                : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]',
            )}
          >
            {t(tab.label)}
          </button>
        ))}
      </div>

      {!q ? (
        <Card>
          <p className="text-sm text-[var(--color-text-muted)]">
            {t('search.typeQuery')}
          </p>
        </Card>
      ) : loading ? (
        <Card>
          <p className="text-sm text-[var(--color-text-muted)]">{t('search.searching')}</p>
        </Card>
      ) : results.length === 0 ? (
        <Card>
          <p className="text-sm text-[var(--color-text-muted)]">
            {t('search.noMatch')}{' '}
            <span className="text-[var(--color-text-soft)]">“{q}”</span>. {t('search.tryDifferent')}
          </p>
        </Card>
      ) : (
        <div className="flex flex-col gap-3">
          {type === 'post' &&
            (results as Post[]).map((p) => <PostCard key={p.id} post={p} />)}
          {type === 'community' &&
            (results as Community[]).map((c) => <CommunityResult key={c.id} community={c} />)}
          {type === 'user' &&
            (results as UserProfile[]).map((u) => <UserResult key={u.id} user={u} />)}
        </div>
      )}

      {hasMore && !loading && (
        <div className="py-2 text-center">
          <button
            type="button"
            onClick={loadMore}
            disabled={loadingMore}
            className="inline-flex items-center gap-1.5 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-4 py-2 text-[13px] font-medium text-[var(--color-text-soft)] transition hover:bg-[var(--color-bg-3)] hover:text-[var(--color-text)] disabled:opacity-60"
          >
            {loadingMore ? t('search.loading') : t('search.loadMore')}
          </button>
        </div>
      )}
    </div>
  );
}

function CommunityResult({ community }: { community: Community }) {
  const { t } = useTranslation();
  return (
    <Link
      to={`/c/${community.slug}`}
      className="flex items-start gap-3 rounded-[14px] border border-[var(--color-border)] bg-[var(--color-bg-1)] px-4 py-3.5 transition hover:border-[var(--color-border-strong)]"
    >
      <Avatar src={community.avatar} alt={community.name} size="md" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <h3 className="truncate text-[15px] font-semibold text-[var(--color-text)]">
            c/{community.slug}
          </h3>
          {community.is_nsfw && (
            <span className="rounded-full border border-[rgba(255,106,138,0.2)] bg-[rgba(255,106,138,0.08)] px-2 py-0.5 text-[10.5px] font-medium text-[var(--color-danger)]">
              NSFW
            </span>
          )}
          {community.is_member && (
            <span className="rounded-full border border-[rgba(97,218,251,0.2)] bg-[rgba(97,218,251,0.08)] px-2 py-0.5 text-[10.5px] font-medium text-[var(--color-accent)]">
              Joined
            </span>
          )}
        </div>
        <p className="font-mono mt-0.5 text-[11.5px] text-[var(--color-text-dim)]">
          {community.member_count.toLocaleString()}{' '}
          {community.member_count === 1 ? t('search.member') : t('search.members')}
        </p>
        {community.description && (
          <p className="mt-1.5 line-clamp-2 text-[13px] text-[var(--color-text-muted)]">
            {community.description}
          </p>
        )}
      </div>
    </Link>
  );
}

function UserResult({ user }: { user: UserProfile }) {
  const { t } = useTranslation();
  return (
    <div className="flex items-center gap-3 rounded-[14px] border border-[var(--color-border)] bg-[var(--color-bg-1)] px-4 py-3.5 transition hover:border-[var(--color-border-strong)]">
      <Link to={`/u/${user.username}`} className="shrink-0">
        <Avatar src={user.avatar} alt={user.username} size="md" />
      </Link>
      <Link to={`/u/${user.username}`} className="min-w-0 flex-1">
        <h3 className="truncate text-[15px] font-semibold text-[var(--color-text)] hover:text-[var(--color-accent)]">
          u/{user.username}
        </h3>
        <p className="font-mono mt-0.5 text-[11.5px] text-[var(--color-text-dim)]">
          ↑ {user.total_karma.toLocaleString()} karma · {user.followers_count.toLocaleString()}{' '}
          {user.followers_count === 1 ? t('search.follower') : t('search.followers')}
        </p>
        {user.bio && (
          <p className="mt-1.5 line-clamp-2 text-[13px] text-[var(--color-text-muted)]">
            {user.bio}
          </p>
        )}
      </Link>
      <FollowButton username={user.username} initialFollowing={user.is_following} size="sm" />
    </div>
  );
}

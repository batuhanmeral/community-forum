import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { deleteFeed, getFeed, listFeedPosts, type CustomFeed } from '@/api/customFeeds';
import type { SortOption } from '@/api/posts';
import { useAppSelector } from '@/app/hooks';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { PageTitle } from '@/components/ui/PageTitle';
import { PostCard } from '@/components/posts/PostCard';
import { PostSortTabs } from '@/components/posts/PostSortTabs';
import { usePagedList } from '@/lib/usePagedList';
import { userPath } from '@/lib/paths';

/** A custom feed: public ones are read-only for visitors, private ones exist only for the owner. */
export function CustomFeedPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { username = '', slug = '' } = useParams<{ username: string; slug: string }>();
  const myUsername = useAppSelector((s) => s.auth.user?.username);
  const [feed, setFeed] = useState<CustomFeed | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [sort, setSort] = useState<SortOption>('new');

  useEffect(() => {
    let cancelled = false;
    setFeed(null);
    setNotFound(false);
    getFeed(username, slug)
      .then((f) => {
        if (!cancelled) setFeed(f);
      })
      .catch(() => {
        if (!cancelled) setNotFound(true);
      });
    return () => {
      cancelled = true;
    };
  }, [username, slug]);

  const fetchPage = useCallback(
    (page: number) => listFeedPosts(username, slug, { sort, page }),
    [username, slug, sort],
  );
  const posts = usePagedList(fetchPage);
  const isOwner = Boolean(myUsername) && myUsername?.toLowerCase() === username.toLowerCase();

  async function handleDelete() {
    await deleteFeed(username, slug);
    navigate('/feeds', { replace: true });
  }

  if (notFound) {
    return (
      <Card>
        <PageTitle title={t('customFeeds.notFound')} />
        <h2 className="text-lg font-semibold">{t('customFeeds.notFound')}</h2>
        <p className="mt-1 text-sm text-[var(--color-text-muted)]">{t('customFeeds.notFoundBody')}</p>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <PageTitle title={feed?.name ?? t('customFeeds.title')} />
      {feed && (
        <Card>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <h1 className="text-2xl font-bold tracking-tight">{feed.name}</h1>
              <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                {t('customFeeds.by')}{' '}
                <Link to={userPath(feed.owner_username)} className="hover:underline">
                  u/{feed.owner_username}
                </Link>{' '}
                · {feed.is_public ? t('customFeeds.public') : t('customFeeds.private')}
              </p>
              {feed.description && <p className="mt-2 text-sm">{feed.description}</p>}
            </div>
            {isOwner && (
              <div className="flex gap-2">
                <Link to="/feeds">
                  <Button variant="secondary" size="sm">
                    {t('customFeeds.manage')}
                  </Button>
                </Link>
                <Button variant="ghost" size="sm" onClick={handleDelete}>
                  {t('common.delete')}
                </Button>
              </div>
            )}
          </div>
          <ul className="mt-3 flex flex-wrap gap-2" aria-label={t('customFeeds.communities')}>
            {feed.communities.map((c) => (
              <li key={c}>
                <Link
                  to={`/c/${c}`}
                  className="rounded-full border border-[var(--color-border)] px-2.5 py-1 text-xs hover:border-[var(--color-link)]"
                >
                  c/{c}
                </Link>
              </li>
            ))}
            {feed.communities.length === 0 && (
              <li className="text-xs text-[var(--color-text-dim)]">{t('customFeeds.noCommunities')}</li>
            )}
          </ul>
        </Card>
      )}
      <PostSortTabs value={sort} onChange={setSort} />
      {posts.loading ? (
        <p className="text-sm text-[var(--color-text-muted)]">{t('common.loading')}</p>
      ) : posts.loadFailed ? (
        <p role="alert" className="text-sm text-[var(--color-danger)]">
          {t('customFeeds.loadFailed')}
        </p>
      ) : posts.items.length === 0 ? (
        <p className="text-sm text-[var(--color-text-muted)]">{t('customFeeds.emptyPosts')}</p>
      ) : (
        posts.items.map((p) => <PostCard key={p.id} post={p} />)
      )}
      {posts.nextPage !== null && (
        <Button variant="secondary" size="sm" onClick={posts.loadMore}>
          {t('common.loadMore')}
        </Button>
      )}
    </div>
  );
}

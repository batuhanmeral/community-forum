import { useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { listHiddenPosts, unhidePost } from '@/api/posts';
import { Button } from '@/components/ui/Button';
import { PageTitle } from '@/components/ui/PageTitle';
import { PostCard } from '@/components/posts/PostCard';
import { usePagedList } from '@/lib/usePagedList';

export function HiddenPostsPage() {
  const { t } = useTranslation();
  const fetchPage = useCallback((page: number) => listHiddenPosts(page), []);
  const list = usePagedList(fetchPage);

  async function unhide(id: number) {
    try {
      await unhidePost(id);
      list.remove(id);
    } catch {
      // Keep the row; the user can try again.
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <PageTitle title={t('titles.hidden')} />
      <h1 className="text-2xl font-bold tracking-tight">{t('titles.hidden')}</h1>
      <p className="text-sm text-[var(--color-text-muted)]">{t('hide.pageHint')}</p>
      {list.loading ? (
        <p className="text-sm text-[var(--color-text-muted)]">{t('common.loading')}</p>
      ) : list.loadFailed ? (
        <p role="alert" className="text-sm text-[var(--color-danger)]">
          {t('hide.loadFailed')}
        </p>
      ) : list.items.length === 0 ? (
        <p className="text-sm text-[var(--color-text-muted)]">{t('hide.empty')}</p>
      ) : (
        list.items.map((post) => (
          <div key={post.id}>
            <PostCard post={post} hideAction />
            <Button variant="secondary" size="sm" className="-mt-1 mb-3" onClick={() => unhide(post.id)}>
              {t('hide.unhide')}
            </Button>
          </div>
        ))
      )}
      {list.nextPage !== null && (
        <Button variant="secondary" size="sm" onClick={list.loadMore}>
          {t('common.loadMore')}
        </Button>
      )}
      {list.loadMoreFailed && (
        <p role="alert" className="text-sm text-[var(--color-danger)]">
          {t('hide.loadFailed')}
        </p>
      )}
    </div>
  );
}

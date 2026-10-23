import { useTranslation } from 'react-i18next';
import type { Paginated } from '@/features/communities/types';
import type { CommentRevision } from '@/features/comments/types';
import type { PostRevision } from '@/features/posts/types';
import { Modal } from '@/components/ui/Modal';
import { usePagedList } from '@/lib/usePagedList';
import { timeAgo } from '@/lib/time';

type Revision = PostRevision | CommentRevision;
type LoadRevisions = (page: number) => Promise<Paginated<Revision>>;

interface EditHistoryModalProps {
  open: boolean;
  onClose: () => void;
  load: LoadRevisions;
}

export function EditHistoryModal({ open, onClose, load }: EditHistoryModalProps) {
  const { t } = useTranslation();
  // Modal renders nothing while closed, so the list (and its fetch) only exists when open.
  return (
    <Modal open={open} onClose={onClose} title={t('history.title')} className="max-w-xl">
      <RevisionList load={load} />
    </Modal>
  );
}

function RevisionList({ load }: { load: LoadRevisions }) {
  const { t } = useTranslation();
  const { items, loading, loadFailed, nextPage, loadMore, loadMoreFailed } = usePagedList(load);

  if (loading) return <p className="text-sm text-[var(--color-text-muted)]">{t('mod.loading')}</p>;
  if (loadFailed) return <p className="text-sm text-[var(--color-danger)]">{t('history.loadFailed')}</p>;
  if (items.length === 0) return <p className="text-sm text-[var(--color-text-muted)]">{t('history.empty')}</p>;

  return (
    <div className="flex max-h-[60vh] flex-col gap-3 overflow-y-auto">
      {items.map((rev) => (
        <article key={rev.id} className="rounded-[10px] border border-[var(--color-border)] px-3 py-2">
          <div className="text-xs text-[var(--color-text-muted)]">
            {rev.edited_by_username && `${t('history.editedBy', { username: rev.edited_by_username })} · `}
            {timeAgo(rev.edited_at)}
          </div>
          {'title' in rev && <p className="mt-1 text-sm font-semibold">{rev.title}</p>}
          <p className="mt-1 whitespace-pre-wrap break-words text-sm text-[var(--color-text-soft)]">
            {rev.body}
          </p>
        </article>
      ))}
      {nextPage !== null && (
        <button type="button" onClick={loadMore} className="text-sm text-[var(--color-link)] hover:underline">
          {t('history.loadMore')}
        </button>
      )}
      {loadMoreFailed && (
        <p className="text-sm text-[var(--color-danger)]">{t('history.loadMoreFailed')}</p>
      )}
    </div>
  );
}

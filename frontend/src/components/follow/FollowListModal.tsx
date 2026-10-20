import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { listFollowers, listFollowing, type FollowUser } from '@/api/follow';
import { Avatar } from '@/components/ui/Avatar';
import { Modal } from '@/components/ui/Modal';
import { userPath } from '@/lib/paths';
import { FollowButton } from './FollowButton';

type Mode = 'followers' | 'following';

interface FollowListModalProps {
  open: boolean;
  onClose: () => void;
  username: string;
  mode: Mode;
}

export function FollowListModal({ open, onClose, username, mode }: FollowListModalProps) {
  const { t } = useTranslation();
  const [loadMoreFailed, setLoadMoreFailed] = useState(false);
  const [users, setUsers] = useState<FollowUser[]>([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setLoadMoreFailed(false);
    setPage(1);
    const fetcher = mode === 'followers' ? listFollowers : listFollowing;
    fetcher(username, 1)
      .then((d) => {
        setUsers(d.results);
        setHasMore(Boolean(d.next));
      })
      .catch(() => undefined)
      .finally(() => setLoading(false));
  }, [open, username, mode]);

  async function loadMore() {
    const next = page + 1;
    const fetcher = mode === 'followers' ? listFollowers : listFollowing;
    setLoading(true);
    setLoadMoreFailed(false);
    try {
      const d = await fetcher(username, next);
      setUsers((u) => [...u, ...d.results]);
      setHasMore(Boolean(d.next));
      setPage(next);
    } catch {
      setLoadMoreFailed(true);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={mode === 'followers' ? `u/${username}'s followers` : `u/${username} is following`}
    >
      <div className="-mx-1 max-h-[60vh] overflow-y-auto">
        {loading && users.length === 0 ? (
          <p className="px-4 py-6 text-center text-sm text-[var(--color-text-muted)]">Loading…</p>
        ) : users.length === 0 ? (
          <p className="px-4 py-6 text-center text-sm text-[var(--color-text-muted)]">
            {mode === 'followers' ? 'No followers yet.' : 'Not following anyone.'}
          </p>
        ) : (
          <ul className="flex flex-col">
            {users.map((u) => (
              <li
                key={u.id}
                className="flex items-center gap-3 rounded-lg px-2 py-2 transition hover:bg-[var(--color-surface)]"
              >
                <Link to={userPath(u.username)} onClick={onClose} className="flex flex-1 items-center gap-3">
                  <Avatar src={u.avatar} alt={u.username} size="sm" />
                  <span className="text-sm font-medium">u/{u.username}</span>
                </Link>
                <FollowButton username={u.username} initialFollowing={u.is_following} size="sm" />
              </li>
            ))}
          </ul>
        )}
        {hasMore && (
          <div className="py-3 text-center">
            <button
              type="button"
              onClick={loadMore}
              disabled={loading}
              className="text-[12px] font-medium text-[var(--color-accent)] hover:underline disabled:opacity-60"
            >
              {loading ? 'Loading…' : 'Load more'}
            </button>
          </div>
        )}
        {loadMoreFailed && (
          <p className="pb-3 text-center text-sm text-[var(--color-danger)]">
            {t('follow.loadMoreFailed')}
          </p>
        )}
      </div>
    </Modal>
  );
}

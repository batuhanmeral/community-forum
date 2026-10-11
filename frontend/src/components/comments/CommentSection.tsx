import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { createComment, listComments } from '@/api/comments';
import type { Comment, CommentSort } from '@/features/comments/types';
import { useAppSelector } from '@/app/hooks';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { CommentForm } from './CommentForm';
import { CommentNode } from './CommentNode';
import { buildCommentTree } from './tree';
import { cn } from '@/lib/cn';

interface CommentSectionProps {
  postId: number;
  canComment?: boolean;
  isModerator?: boolean;
}

const SORTS: Array<{ value: CommentSort; label: string }> = [
  { value: 'best', label: 'Best' },
  { value: 'top', label: 'Top' },
  { value: 'new', label: 'New' },
  { value: 'old', label: 'Old' },
  { value: 'controversial', label: 'Controversial' },
];

export function CommentSection({ postId, canComment = true, isModerator = false }: CommentSectionProps) {
  const { t } = useTranslation();
  const isAuthed = useAppSelector((s) => s.auth.status === 'authenticated');
  const [comments, setComments] = useState<Comment[]>([]);
  const [sort, setSort] = useState<CommentSort>('best');
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [nextPage, setNextPage] = useState<number | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [loadMoreFailed, setLoadMoreFailed] = useState(false);
  // Bumped on every (re)fetch and unmount so late load-more responses can be discarded.
  const listVersion = useRef(0);

  useEffect(() => {
    let cancelled = false;
    listVersion.current++;
    setLoading(true);
    setNextPage(null);
    setLoadMoreFailed(false);
    setLoadingMore(false);
    listComments(postId, { sort })
      .then((d) => {
        if (cancelled) return;
        setComments(d.results);
        setTotal(d.count);
        setNextPage(d.next ? 2 : null);
      })
      .catch(() => undefined)
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [postId, sort]);

  const location = useLocation();

  const scrolledHash = useRef('');

  // Notification links point at #comment-<id>; scroll there once per hash so a sort change doesn't yank the viewport back.
  useEffect(() => {
    if (loading || !location.hash.startsWith('#comment-')) return;
    if (scrolledHash.current === location.hash) return;
    const el = document.getElementById(location.hash.slice(1));
    if (!el) return;
    el.scrollIntoView({ block: 'center' });
    scrolledHash.current = location.hash;
  }, [loading, location.hash]);

  // Invalidates any in-flight load-more after unmount.
  useEffect(
    () => () => {
      listVersion.current = -1;
    },
    [],
  );

  async function loadMore() {
    if (nextPage === null) return;
    const version = listVersion.current;
    setLoadingMore(true);
    setLoadMoreFailed(false);
    try {
      const d = await listComments(postId, { sort, page: nextPage });
      if (version !== listVersion.current) return;
      // Pages shift when someone comments meanwhile, so the next page can repeat loaded ids.
      setComments((cs) => {
        const loaded = new Set(cs.map((c) => c.id));
        return [...cs, ...d.results.filter((c) => !loaded.has(c.id))];
      });
      setNextPage(d.next ? nextPage + 1 : null);
    } catch {
      if (version === listVersion.current) setLoadMoreFailed(true);
    } finally {
      if (version === listVersion.current) setLoadingMore(false);
    }
  }

  async function handleNewRoot(body: string) {
    const created = await createComment(postId, body, null);
    setComments((cs) => [created, ...cs]);
    setTotal((n) => n + 1);
  }

  function handleReply(_parentId: number, created: Comment) {
    setComments((cs) => [...cs, created]);
    setTotal((n) => n + 1);
  }

  function handleUpdate(updated: Comment) {
    setComments((cs) => cs.map((c) => (c.id === updated.id ? updated : c)));
  }

  function handleDelete(id: number) {
    setComments((cs) =>
      cs.map((c) =>
        c.id === id
          ? { ...c, is_deleted: true, author: null, author_username: null, body: '[deleted]', body_html: '<p>[deleted]</p>' }
          : c,
      ),
    );
  }

  const tree = buildCommentTree(comments);

  return (
    <Card>
      <div className="flex items-center justify-between gap-2 border-b border-[var(--color-border)] pb-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
          {t('comments.count', { count: total })}
        </h2>
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value as CommentSort)}
          className="rounded-full border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-1 text-xs focus:border-[var(--color-accent)] focus:outline-none"
        >
          {SORTS.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
      </div>

      {canComment && (
        <div className="mt-4">
          {isAuthed ? (
            <CommentForm placeholder="Add a comment..." onSubmit={handleNewRoot} />
          ) : (
            <p className="text-sm text-[var(--color-text-muted)]">
              <Link to="/login" className="text-[var(--color-accent)] hover:underline">
                Log in
              </Link>{' '}
              to leave a comment.
            </p>
          )}
        </div>
      )}

      <div className={cn('mt-4 flex flex-col gap-3', !tree.length && 'hidden')}>
        {tree.map((node) => (
          <CommentNode
            key={node.id}
            node={node}
            postId={postId}
            depth={0}
            isModerator={isModerator}
            onReply={handleReply}
            onUpdate={handleUpdate}
            onDelete={handleDelete}
          />
        ))}
      </div>

      {nextPage !== null && (
        <Button
          variant="secondary"
          size="sm"
          className="mt-4"
          loading={loadingMore}
          onClick={loadMore}
        >
          {t('comments.loadMore')}
        </Button>
      )}
      {loadMoreFailed && (
        <p role="alert" className="mt-2 text-sm text-[var(--color-danger)]">
          {t('comments.loadMoreFailed')}
        </p>
      )}

      {loading && (
        <p className="mt-4 text-sm text-[var(--color-text-muted)]">Loading comments…</p>
      )}
      {!loading && comments.length === 0 && (
        <p className="mt-4 text-sm text-[var(--color-text-muted)]">
          No comments yet. Be the first to weigh in.
        </p>
      )}
    </Card>
  );
}

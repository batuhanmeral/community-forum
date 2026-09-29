import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { createComment, listComments } from '@/api/comments';
import type { Comment, CommentSort } from '@/features/comments/types';
import { useAppSelector } from '@/app/hooks';
import { Card } from '@/components/ui/Card';
import { CommentForm } from './CommentForm';
import { CommentNode } from './CommentNode';
import { buildCommentTree } from './tree';
import { cn } from '@/lib/cn';

interface CommentSectionProps {
  postId: number;
  canComment?: boolean;
}

const SORTS: Array<{ value: CommentSort; label: string }> = [
  { value: 'best', label: 'Best' },
  { value: 'top', label: 'Top' },
  { value: 'new', label: 'New' },
  { value: 'old', label: 'Old' },
  { value: 'controversial', label: 'Controversial' },
];

export function CommentSection({ postId, canComment = true }: CommentSectionProps) {
  const isAuthed = useAppSelector((s) => s.auth.status === 'authenticated');
  const [comments, setComments] = useState<Comment[]>([]);
  const [sort, setSort] = useState<CommentSort>('best');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listComments(postId, { sort })
      .then((d) => {
        if (!cancelled) setComments(d.results);
      })
      .catch(() => undefined)
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [postId, sort]);

  async function handleNewRoot(body: string) {
    const created = await createComment(postId, body, null);
    setComments((cs) => [created, ...cs]);
  }

  function handleReply(_parentId: number, created: Comment) {
    setComments((cs) => [...cs, created]);
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
          {comments.length} comment{comments.length === 1 ? '' : 's'}
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
            onReply={handleReply}
            onUpdate={handleUpdate}
            onDelete={handleDelete}
          />
        ))}
      </div>

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

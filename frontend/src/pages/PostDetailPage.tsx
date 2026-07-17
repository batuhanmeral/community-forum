import { useEffect, useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { deletePost, getPost, updatePost } from '@/api/posts';
import type { Post } from '@/features/posts/types';
import { useAppSelector } from '@/app/hooks';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { CommentSection } from '@/components/comments/CommentSection';
import { timeAgo } from '@/lib/time';
import { cn } from '@/lib/cn';

export function PostDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const currentUserId = useAppSelector((s) => s.auth.user?.id);

  const [post, setPost] = useState<Post | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    setLoading(true);
    setNotFound(false);
    getPost(Number(id))
      .then((p) => {
        if (!cancelled) setPost(p);
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
  }, [id]);

  async function handleDelete() {
    if (!post) return;
    await deletePost(post.id);
    navigate(`/c/${post.community}`, { replace: true });
  }

  if (loading) return <p className="text-sm text-[var(--color-text-muted)]">Loading…</p>;
  if (notFound || !post) {
    return (
      <Card>
        <h2 className="text-lg font-semibold">Post not found</h2>
        <p className="mt-1 text-sm text-[var(--color-text-muted)]">
          This post may have been removed.
        </p>
      </Card>
    );
  }

  const isAuthor = currentUserId !== undefined && post.author === currentUserId;
  const canEdit = isAuthor && (post.kind === 'text' || post.kind === 'link');

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <Card>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-[var(--color-text-muted)]">
          <Link to={`/c/${post.community}`} className="font-semibold text-[var(--color-text)] hover:underline">
            c/{post.community}
          </Link>
          <span className="text-[var(--color-text-dim)]">·</span>
          <span>{timeAgo(post.created_at)}</span>
          {post.edited_at && <span className="italic">(edited)</span>}
          {post.is_pinned && <Badge tone="accent">Pinned</Badge>}
          {post.is_nsfw && <Badge tone="danger">NSFW</Badge>}
        </div>

        {editing ? (
          <PostEditForm
            post={post}
            onCancel={() => setEditing(false)}
            onSaved={(updated) => {
              setPost(updated);
              setEditing(false);
            }}
          />
        ) : (
          <>
            <h1 className="mt-2 text-2xl font-bold tracking-tight">{post.title}</h1>

            {post.kind === 'link' && post.url && (
              <a
                href={post.url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 inline-flex items-center gap-1 text-sm text-[var(--color-accent)] hover:underline break-all"
              >
                {post.url}
              </a>
            )}

            {post.kind === 'image' && post.image && (
              <div className="mt-3 overflow-hidden rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-elevated)]">
                <img
                  src={post.image}
                  alt={post.title}
                  className={cn(
                    'max-h-[600px] w-full object-contain',
                    post.is_nsfw && 'blur-2xl hover:blur-0 transition',
                  )}
                />
              </div>
            )}

            {post.kind === 'text' && post.body_html && (
              <div
                className="prose-nexus mt-3 text-sm text-[var(--color-text)]"
                dangerouslySetInnerHTML={{ __html: post.body_html }}
              />
            )}

            {post.kind === 'text' && !post.body_html && post.body && (
              <p className="mt-3 whitespace-pre-wrap text-sm">{post.body}</p>
            )}

            {post.kind === 'poll' && post.poll && (
              <Card className="mt-3 bg-[var(--color-bg-elevated)]">
                <p className="text-sm text-[var(--color-text-muted)]">
                  Poll · {post.poll.total_votes} vote{post.poll.total_votes === 1 ? '' : 's'} ·{' '}
                  {post.poll.is_closed ? 'Closed' : `closes ${timeAgo(post.poll.closes_at)}`}
                </p>
                <ul className="mt-3 space-y-2">
                  {post.poll.options.map((opt) => (
                    <li
                      key={opt.id}
                      className="rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm"
                    >
                      <div className="flex items-center justify-between">
                        <span>{opt.text}</span>
                        <span className="text-xs text-[var(--color-text-muted)]">
                          {opt.percent.toFixed(0)}% · {opt.vote_count}
                        </span>
                      </div>
                      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-[var(--color-surface-hover)]">
                        <div
                          className="h-full bg-[var(--color-accent)]"
                          style={{ width: `${opt.percent}%` }}
                        />
                      </div>
                    </li>
                  ))}
                </ul>
              </Card>
            )}

            <div className="mt-4 flex items-center gap-2 border-t border-[var(--color-border)] pt-3 text-sm text-[var(--color-text-muted)]">
              <span className="font-semibold text-[var(--color-text)]">{post.score}</span>
              <span>points</span>
              {isAuthor && (
                <div className="ml-auto flex gap-2">
                  {canEdit && (
                    <Button variant="secondary" size="sm" onClick={() => setEditing(true)}>
                      Edit
                    </Button>
                  )}
                  <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(true)}>
                    Delete
                  </Button>
                </div>
              )}
            </div>
          </>
        )}
      </Card>

      <CommentSection postId={post.id} />

      <Modal
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        title="Delete this post?"
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirmDelete(false)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={handleDelete}>
              Delete
            </Button>
          </>
        }
      >
        <p className="text-sm text-[var(--color-text-muted)]">
          This action cannot be undone. The post will be removed from your community.
        </p>
      </Modal>
    </div>
  );
}

interface EditFormProps {
  post: Post;
  onCancel: () => void;
  onSaved: (p: Post) => void;
}

function PostEditForm({ post, onCancel, onSaved }: EditFormProps) {
  const [title, setTitle] = useState(post.title);
  const [body, setBody] = useState(post.body);
  const [isNsfw, setIsNsfw] = useState(post.is_nsfw);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const updated = await updatePost(post.id, {
        title: title.trim(),
        body: post.kind === 'text' ? body : undefined,
        is_nsfw: isNsfw,
      });
      onSaved(updated);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mt-3 flex flex-col gap-3">
      <Input
        name="title"
        label="Title"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        required
        maxLength={300}
      />
      {post.kind === 'text' && (
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-muted)]">
            Body
          </label>
          <textarea
            rows={8}
            value={body}
            onChange={(e) => setBody(e.target.value)}
            className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-2 text-sm focus:border-[var(--color-accent)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]/30"
          />
        </div>
      )}
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={isNsfw}
          onChange={(e) => setIsNsfw(e.target.checked)}
          className="h-4 w-4 accent-[var(--color-accent)]"
        />
        NSFW
      </label>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" loading={saving}>
          Save
        </Button>
      </div>
    </form>
  );
}

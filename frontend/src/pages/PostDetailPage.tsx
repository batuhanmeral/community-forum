import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { deletePost, getPost, listPostRevisions, setPostSticky, updatePost } from '@/api/posts';
import { getCommunity } from '@/api/communities';
import type { Post } from '@/features/posts/types';
import type { CommunityRole } from '@/features/communities/types';
import { useAppSelector } from '@/app/hooks';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { PageTitle } from '@/components/ui/PageTitle';
import { Modal } from '@/components/ui/Modal';
import { CommentSection } from '@/components/comments/CommentSection';
import { NsfwReveal } from '@/components/posts/NsfwReveal';
import { PollCard } from '@/components/posts/PollCard';
import { SaveButton } from '@/components/saves/SaveButton';
import { ReportModal } from '@/components/moderation/ReportModal';
import { EditHistoryModal } from '@/components/revisions/EditHistoryModal';
import { VoteCluster } from '@/components/votes/VoteCluster';
import type { VoteValue } from '@/api/votes';
import { userPath } from '@/lib/paths';
import { timeAgo } from '@/lib/time';

export function PostDetailPage() {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const currentUserId = useAppSelector((s) => s.auth.user?.id);
  const isAuthed = useAppSelector((s) => s.auth.status === 'authenticated');

  const [post, setPost] = useState<Post | null>(null);
  const [myRole, setMyRole] = useState<CommunityRole | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [reporting, setReporting] = useState(false);
  const [stickyBusy, setStickyBusy] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const loadRevisions = useCallback((page: number) => listPostRevisions(Number(id), page), [id]);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    setLoading(true);
    setNotFound(false);
    setMyRole(null);
    getPost(Number(id))
      .then((p) => {
        if (cancelled) return;
        setPost(p);
        if (isAuthed) {
          getCommunity(p.community)
            .then((c) => {
              if (!cancelled) setMyRole(c.my_role);
            })
            .catch(() => undefined);
        }
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
  }, [id, isAuthed]);

  async function handleDelete() {
    if (!post) return;
    await deletePost(post.id);
    navigate(`/c/${post.community}`, { replace: true });
  }

  async function handleSticky() {
    if (!post || stickyBusy) return;
    const next = !post.is_pinned;
    setStickyBusy(true);
    try {
      const res = await setPostSticky(post.id, next);
      setPost({ ...post, is_pinned: res.is_pinned });
    } finally {
      setStickyBusy(false);
    }
  }

  if (loading) return <p className="text-sm text-[var(--color-text-muted)]">{t('common.loading')}</p>;
  if (notFound || !post) {
    return (
      <Card>
        <PageTitle title={t('postPage.notFound')} />
        <h2 className="text-lg font-semibold">{t('postPage.notFound')}</h2>
        <p className="mt-1 text-sm text-[var(--color-text-muted)]">
          {t('postPage.notFoundBody')}
        </p>
      </Card>
    );
  }

  const isAuthor = currentUserId !== undefined && post.author === currentUserId;
  const canEdit = isAuthor && (post.kind === 'text' || post.kind === 'link');
  const isMod = myRole === 'admin' || myRole === 'moderator';
  const canReport = isAuthed && !isAuthor;

  const image = post.image && (
    <img src={post.image} alt={post.title} className="max-h-[600px] w-full object-contain" />
  );

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <PageTitle title={post.title} />
      <Card>
        {!post.is_approved && !post.is_deleted && (
          <p
            role="status"
            className="mb-3 rounded-[10px] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-2 text-sm text-[var(--color-text-soft)]"
          >
            {t('post.pendingApproval')}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-[var(--color-text-muted)]">
          <Link to={`/c/${post.community}`} className="font-semibold text-[var(--color-text)] hover:underline">
            c/{post.community}
          </Link>
          <span className="text-[var(--color-text-dim)]">·</span>
          {post.author_username ? (
            <Link to={userPath(post.author_username)} className="hover:underline">
              u/{post.author_username}
            </Link>
          ) : (
            <span>u/{t('common.deleted')}</span>
          )}
          <span className="text-[var(--color-text-dim)]">·</span>
          <span>{timeAgo(post.created_at)}</span>
          {post.edited_at &&
            (!post.is_deleted && (isAuthor || isMod) ? (
              <button type="button" onClick={() => setHistoryOpen(true)} className="italic hover:underline">
                {t('post.edited')}
              </button>
            ) : (
              <span className="italic">{t('post.edited')}</span>
            ))}
          {post.flair_detail && (
            <span
              className="inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium"
              style={{
                color: post.flair_detail.color,
                borderColor: `${post.flair_detail.color}44`,
                background: `${post.flair_detail.color}14`,
              }}
            >
              {post.flair_detail.name}
            </span>
          )}
          {post.is_pinned && <Badge tone="accent">{t('post.pinned')}</Badge>}
          {post.is_nsfw && <Badge tone="danger">{t('post.nsfw')}</Badge>}
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
                {post.is_nsfw ? <NsfwReveal>{image}</NsfwReveal> : image}
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
              <div className="mt-3">
                <PollCard
                  poll={post.poll}
                  onUpdate={(updated) => setPost({ ...post, poll: updated })}
                />
              </div>
            )}

            <div className="mt-4 flex items-center gap-3 border-t border-[var(--color-border)] pt-3 text-sm text-[var(--color-text-muted)]">
              <VoteCluster
                target="post"
                objectId={post.id}
                score={post.score}
                userVote={post.user_vote as VoteValue | null}
                onChange={({ score, userVote }) => setPost({ ...post, score, user_vote: userVote })}
              />
              <SaveButton
                target="post"
                objectId={post.id}
                initialSaved={post.is_saved}
                onChange={(saved) => setPost({ ...post, is_saved: saved })}
              />
              <div className="ml-auto flex items-center gap-2">
                {isMod && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={handleSticky}
                    loading={stickyBusy}
                  >
                    {post.is_pinned ? t('postPage.unpin') : t('postPage.pin')}
                  </Button>
                )}
                {canReport && (
                  <Button variant="ghost" size="sm" onClick={() => setReporting(true)}>
                    {t('common.report')}
                  </Button>
                )}
                {canEdit && (
                  <Button variant="secondary" size="sm" onClick={() => setEditing(true)}>
                    {t('common.edit')}
                  </Button>
                )}
                {(isAuthor || isMod) && (
                  <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(true)}>
                    {isAuthor ? t('common.delete') : t('postPage.remove')}
                  </Button>
                )}
              </div>
            </div>
          </>
        )}
      </Card>

      <CommentSection
        postId={post.id}
        canComment={!post.is_deleted && post.is_approved}
        isModerator={isMod}
      />

      <Modal
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        title={t('postPage.deleteTitle')}
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirmDelete(false)}>
              {t('common.cancel')}
            </Button>
            <Button variant="danger" onClick={handleDelete}>
              {t('common.delete')}
            </Button>
          </>
        }
      >
        <p className="text-sm text-[var(--color-text-muted)]">
          {t('postPage.deleteBody')}
        </p>
      </Modal>

      <ReportModal
        open={reporting}
        onClose={() => setReporting(false)}
        target="post"
        objectId={post.id}
      />

      <EditHistoryModal open={historyOpen} onClose={() => setHistoryOpen(false)} load={loadRevisions} />
    </div>
  );
}

interface EditFormProps {
  post: Post;
  onCancel: () => void;
  onSaved: (p: Post) => void;
}

function PostEditForm({ post, onCancel, onSaved }: EditFormProps) {
  const { t } = useTranslation();
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
        label={t('postForm.title')}
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        required
        maxLength={300}
      />
      {post.kind === 'text' && (
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-muted)]">
            {t('postForm.body')}
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
        {t('post.nsfw')}
      </label>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="secondary" onClick={onCancel}>
          {t('common.cancel')}
        </Button>
        <Button type="submit" loading={saving}>
          {t('common.save')}
        </Button>
      </div>
    </form>
  );
}

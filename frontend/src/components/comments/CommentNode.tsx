import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { Comment } from '@/features/comments/types';
import { createComment, deleteComment, updateComment } from '@/api/comments';
import { VoteCluster } from '@/components/votes/VoteCluster';
import type { VoteValue } from '@/api/votes';
import { toggleSave } from '@/api/saves';
import { useAppSelector } from '@/app/hooks';
import { ReportModal } from '@/components/moderation/ReportModal';
import { CommentForm } from './CommentForm';
import { timeAgo } from '@/lib/time';
import { cn } from '@/lib/cn';

export interface CommentWithChildren extends Comment {
  children: CommentWithChildren[];
}

interface CommentNodeProps {
  node: CommentWithChildren;
  postId: number;
  depth: number;
  onReply: (parentId: number, created: Comment) => void;
  onUpdate: (updated: Comment) => void;
  onDelete: (id: number) => void;
}

export function CommentNode({ node, postId, depth, onReply, onUpdate, onDelete }: CommentNodeProps) {
  const currentUserId = useAppSelector((s) => s.auth.user?.id);
  const isAuthed = useAppSelector((s) => s.auth.status === 'authenticated');
  const [replying, setReplying] = useState(false);
  const [editing, setEditing] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [reporting, setReporting] = useState(false);

  const isAuthor = currentUserId !== undefined && node.author === currentUserId;
  const canModify = isAuthor && !node.is_deleted;
  const canReport = isAuthed && !isAuthor && !node.is_deleted;

  async function handleEdit(body: string) {
    const updated = await updateComment(node.id, body);
    onUpdate(updated);
    setEditing(false);
  }

  async function handleDelete() {
    await deleteComment(node.id);
    onDelete(node.id);
  }

  return (
    <div className={cn('flex gap-2', depth > 0 && 'mt-3')}>
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        className="mt-1 flex w-3 shrink-0 cursor-pointer items-stretch rounded transition-colors hover:bg-[var(--color-surface-hover)]"
        aria-label={collapsed ? 'Expand' : 'Collapse'}
      >
        <span className="m-auto block h-full w-px bg-[var(--color-border)]" />
      </button>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-[var(--color-text-muted)]">
          {node.author_username ? (
            <Link
              to={`/u/${node.author_username}`}
              className="font-semibold text-[var(--color-text)] hover:underline"
            >
              {node.author_username}
            </Link>
          ) : (
            <span className="italic">[deleted]</span>
          )}
          <span className="text-[var(--color-text-dim)]">·</span>
          <span>{timeAgo(node.created_at)}</span>
          {node.edited_at && <span className="italic">(edited)</span>}
        </div>

        {!collapsed && (
          <>
            {editing ? (
              <div className="mt-2">
                <CommentForm
                  initialValue={node.body}
                  submitLabel="Save"
                  autoFocus
                  onSubmit={handleEdit}
                  onCancel={() => setEditing(false)}
                />
              </div>
            ) : (
              <div
                className="prose-nexus mt-1 text-sm text-[var(--color-text)]"
                dangerouslySetInnerHTML={{ __html: node.body_html }}
              />
            )}

            {!editing && !node.is_deleted && (
              <div className="mt-1.5 flex items-center gap-3 text-xs text-[var(--color-text-muted)]">
                <VoteCluster
                  target="comment"
                  objectId={node.id}
                  score={node.score}
                  userVote={node.user_vote as VoteValue | null}
                  size="sm"
                />
                <button
                  type="button"
                  onClick={() => setReplying((r) => !r)}
                  className="hover:text-[var(--color-text)]"
                >
                  Reply
                </button>
                <CommentSaveLink commentId={node.id} initialSaved={node.is_saved} />
                {canReport && (
                  <button
                    type="button"
                    onClick={() => setReporting(true)}
                    className="hover:text-[var(--color-danger)]"
                  >
                    Report
                  </button>
                )}
                {canModify && (
                  <>
                    <button
                      type="button"
                      onClick={() => setEditing(true)}
                      className="hover:text-[var(--color-text)]"
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={handleDelete}
                      className="hover:text-[var(--color-danger)]"
                    >
                      Delete
                    </button>
                  </>
                )}
              </div>
            )}

            {replying && (
              <div className="mt-2">
                <CommentForm
                  autoFocus
                  placeholder={`Reply to ${node.author_username ?? 'comment'}...`}
                  submitLabel="Reply"
                  onCancel={() => setReplying(false)}
                  onSubmit={async (body) => {
                    const created = await createComment(postId, body, node.id);
                    onReply(node.id, created);
                    setReplying(false);
                  }}
                />
              </div>
            )}

            {node.children.length > 0 && (
              <div className="mt-2">
                {node.children.map((child) => (
                  <CommentNode
                    key={child.id}
                    node={child}
                    postId={postId}
                    depth={depth + 1}
                    onReply={onReply}
                    onUpdate={onUpdate}
                    onDelete={onDelete}
                  />
                ))}
              </div>
            )}
          </>
        )}

        {collapsed && node.children.length > 0 && (
          <button
            type="button"
            onClick={() => setCollapsed(false)}
            className="mt-1 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          >
            [+] {node.children.length} more {node.children.length === 1 ? 'reply' : 'replies'}
          </button>
        )}
      </div>

      <ReportModal
        open={reporting}
        onClose={() => setReporting(false)}
        target="comment"
        objectId={node.id}
        label="comment"
      />
    </div>
  );
}

function CommentSaveLink({ commentId, initialSaved }: { commentId: number; initialSaved: boolean }) {
  const [saved, setSaved] = useState(initialSaved);
  const [busy, setBusy] = useState(false);
  async function handleClick() {
    if (busy) return;
    const prev = saved;
    setSaved(!prev);
    setBusy(true);
    try {
      const res = await toggleSave('comment', commentId);
      if (res.is_saved !== !prev) setSaved(res.is_saved);
    } catch {
      setSaved(prev);
    } finally {
      setBusy(false);
    }
  }
  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={busy}
      className={saved ? 'text-[var(--color-accent)] hover:opacity-80' : 'hover:text-[var(--color-text)]'}
    >
      {saved ? 'Saved' : 'Save'}
    </button>
  );
}

export function buildCommentTree(comments: Comment[]): CommentWithChildren[] {
  const byId = new Map<number, CommentWithChildren>();
  const roots: CommentWithChildren[] = [];
  for (const c of comments) {
    byId.set(c.id, { ...c, children: [] });
  }
  for (const c of comments) {
    const node = byId.get(c.id);
    if (!node) continue;
    if (c.parent && byId.has(c.parent)) {
      byId.get(c.parent)!.children.push(node);
    } else {
      roots.push(node);
    }
  }
  return roots;
}

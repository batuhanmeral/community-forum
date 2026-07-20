import type { Comment } from '@/features/comments/types';

export interface CommentWithChildren extends Comment {
  children: CommentWithChildren[];
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

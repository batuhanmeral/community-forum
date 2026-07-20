import { describe, it, expect } from 'vitest';
import { buildCommentTree } from './CommentNode';
import type { Comment } from '@/features/comments/types';

function c(id: number, parent: number | null): Comment {
  return {
    id,
    post: 1,
    author: 1,
    author_username: 'alice',
    parent,
    body: `comment ${id}`,
    body_html: `<p>comment ${id}</p>`,
    is_deleted: false,
    score: 0,
    user_vote: null,
    is_saved: false,
    created_at: '2026-06-24T12:00:00Z',
    updated_at: '2026-06-24T12:00:00Z',
    edited_at: null,
  };
}

describe('buildCommentTree', () => {
  it('nests replies under their parent', () => {
    const tree = buildCommentTree([c(1, null), c(2, 1), c(3, 1), c(4, 2)]);
    expect(tree).toHaveLength(1);
    expect(tree[0].id).toBe(1);
    expect(tree[0].children.map((n) => n.id)).toEqual([2, 3]);
    expect(tree[0].children[0].children.map((n) => n.id)).toEqual([4]);
  });

  it('treats multiple top-level comments as roots', () => {
    const tree = buildCommentTree([c(1, null), c(2, null)]);
    expect(tree.map((n) => n.id)).toEqual([1, 2]);
  });

  it('promotes orphaned replies (missing parent) to roots', () => {
    const tree = buildCommentTree([c(2, 99)]);
    expect(tree).toHaveLength(1);
    expect(tree[0].id).toBe(2);
  });

  it('returns an empty array for no comments', () => {
    expect(buildCommentTree([])).toEqual([]);
  });
});

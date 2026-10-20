import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer from '@/features/auth/authSlice';
import type { Post } from '@/features/posts/types';
import { PostCard } from './PostCard';

vi.mock('@/api/votes', () => ({ castVote: vi.fn() }));
vi.mock('@/api/saves', () => ({ toggleSave: vi.fn() }));

function makePost(overrides: Partial<Post> = {}): Post {
  return {
    id: 1,
    author: 7,
    author_username: 'alice',
    community: 'py',
    flair: null,
    flair_detail: null,
    kind: 'text',
    title: 'Hello',
    body: 'Body',
    body_html: '<p>Body</p>',
    is_deleted: false,
    url: '',
    image: null,
    is_nsfw: false,
    is_pinned: false,
    is_approved: true,
    score: 0,
    comment_count: 0,
    user_vote: null,
    is_saved: false,
    poll: null,
    created_at: '2026-10-01T00:00:00Z',
    edited_at: null,
    ...overrides,
  };
}

function renderCard(post: Post) {
  const store = configureStore({ reducer: { auth: authReducer } });
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <PostCard post={post} />
      </MemoryRouter>
    </Provider>,
  );
}

describe('PostCard', () => {
  it('links the author through userPath', () => {
    renderCard(makePost({ author_username: 'a b' }));
    expect(screen.getByRole('link', { name: 'u/a b' })).toHaveAttribute('href', '/u/a%20b');
  });

  it.each(['text', 'link', 'image', 'poll'] as const)('a %s card has no nested anchors', (kind) => {
    const post = makePost({
      kind,
      url: kind === 'link' ? 'https://example.com/x' : '',
      image: kind === 'image' ? 'https://example.com/i.png' : null,
      poll:
        kind === 'poll'
          ? {
              id: 1,
              options: [{ id: 1, text: 'A', order: 0, vote_count: 1, percent: 100 }],
              total_votes: 1,
              closes_at: '2026-12-01T00:00:00Z',
              is_closed: false,
              user_option: null,
            }
          : null,
    });
    const { container } = renderCard(post);
    expect(container.querySelectorAll('a a')).toHaveLength(0);
  });

  it('the title links to the post', () => {
    renderCard(makePost({ title: 'Hello' }));
    expect(screen.getByRole('link', { name: 'Hello' })).toHaveAttribute('href', '/posts/1');
  });

  it('the external link opens in a new tab without referrer', () => {
    renderCard(makePost({ kind: 'link', url: 'https://example.com/x' }));
    const link = screen.getByRole('link', { name: /External link/ });
    expect(link).toHaveAttribute('href', 'https://example.com/x');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link.getAttribute('rel')).toContain('noopener');
    expect(link.getAttribute('rel')).toContain('noreferrer');
  });
});

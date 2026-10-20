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
});

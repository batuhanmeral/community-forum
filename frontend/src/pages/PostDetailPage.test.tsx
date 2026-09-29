import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer, { setUser } from '@/features/auth/authSlice';
import type { Post } from '@/features/posts/types';
import { PostDetailPage } from './PostDetailPage';
import * as postsApi from '@/api/posts';
import * as communitiesApi from '@/api/communities';
import * as commentsApi from '@/api/comments';

vi.mock('@/api/posts', () => ({
  getPost: vi.fn(),
  deletePost: vi.fn(),
  setPostSticky: vi.fn(),
  updatePost: vi.fn(),
}));
vi.mock('@/api/communities', () => ({ getCommunity: vi.fn() }));
vi.mock('@/api/comments', () => ({ listComments: vi.fn(), createComment: vi.fn() }));
vi.mock('@/api/search', () => ({ searchUsers: vi.fn() }));

const basePost = {
  id: 5,
  author: 9,
  author_username: 'bob',
  community: 'py',
  flair: null,
  flair_detail: null,
  kind: 'text',
  title: 'Title',
  body: 'body',
  body_html: '<p>body</p>',
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
} as unknown as Post;

function renderPage() {
  const store = configureStore({ reducer: { auth: authReducer } });
  store.dispatch(
    setUser({
      id: 1,
      username: 'alice',
      email: 'a@x.com',
      email_verified: true,
      avatar: null,
      bio: '',
      show_nsfw: false,
      post_karma: 0,
      comment_karma: 0,
    }),
  );
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/posts/5']}>
        <Routes>
          <Route path="/posts/:id" element={<PostDetailPage />} />
        </Routes>
      </MemoryRouter>
    </Provider>,
  );
}

describe('PostDetailPage comment form', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(commentsApi.listComments).mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    });
    vi.mocked(communitiesApi.getCommunity).mockRejectedValue(new Error('skip'));
  });

  it('shows the form on an open post', async () => {
    vi.mocked(postsApi.getPost).mockResolvedValue(basePost);
    renderPage();
    expect(await screen.findByPlaceholderText('Add a comment...')).toBeInTheDocument();
  });

  it('hides the form on a deleted post', async () => {
    vi.mocked(postsApi.getPost).mockResolvedValue({ ...basePost, is_deleted: true });
    renderPage();
    expect(await screen.findByText(/comments?$/i)).toBeInTheDocument();
    expect(screen.queryByPlaceholderText('Add a comment...')).not.toBeInTheDocument();
  });

  it('hides the form on an unapproved post', async () => {
    vi.mocked(postsApi.getPost).mockResolvedValue({ ...basePost, is_approved: false });
    renderPage();
    expect(await screen.findByText(/comments?$/i)).toBeInTheDocument();
    expect(screen.queryByPlaceholderText('Add a comment...')).not.toBeInTheDocument();
  });
});

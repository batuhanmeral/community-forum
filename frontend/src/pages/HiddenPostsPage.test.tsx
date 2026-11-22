import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer from '@/features/auth/authSlice';
import type { Post } from '@/features/posts/types';
import { HiddenPostsPage } from './HiddenPostsPage';
import * as postsApi from '@/api/posts';

vi.mock('@/api/posts', () => ({ listHiddenPosts: vi.fn(), unhidePost: vi.fn(), hidePost: vi.fn() }));
vi.mock('@/api/votes', () => ({ castVote: vi.fn() }));
vi.mock('@/api/saves', () => ({ toggleSave: vi.fn() }));

const post = {
  id: 4,
  author: 1,
  author_username: 'bob',
  community: 'py',
  flair: null,
  flair_detail: null,
  kind: 'text',
  title: 'Hidden one',
  body: 'b',
  body_html: '<p>b</p>',
  is_deleted: false,
  url: '',
  image: null,
  is_nsfw: false,
  crosspost_from: null,
  is_spoiler: false,
  is_question: false,
  accepted_comment: null,
  bounty_amount: 0,
  bounty_expires_at: null,
  bounty_status: '',
  is_pinned: false,
  is_approved: true,
  score: 0,
  comment_count: 0,
  user_vote: null,
  is_saved: false,
  poll: null,
  created_at: '2026-10-01T00:00:00Z',
  edited_at: null,
} as Post;

function renderPage() {
  const store = configureStore({ reducer: { auth: authReducer } });
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <HiddenPostsPage />
      </MemoryRouter>
    </Provider>,
  );
}

describe('HiddenPostsPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('lists hidden posts and unhides one', async () => {
    vi.mocked(postsApi.listHiddenPosts).mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [post],
    });
    vi.mocked(postsApi.unhidePost).mockResolvedValue();
    renderPage();
    expect(await screen.findByText('Hidden one')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Unhide' }));
    expect(postsApi.unhidePost).toHaveBeenCalledWith(4);
    expect(await screen.findByText('You have not hidden any posts.')).toBeInTheDocument();
  });

  it('shows an error when the list cannot load', async () => {
    vi.mocked(postsApi.listHiddenPosts).mockRejectedValue(new Error('x'));
    renderPage();
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load hidden posts.');
  });
});

import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer from '@/features/auth/authSlice';
import type { Comment } from '@/features/comments/types';
import type { Post } from '@/features/posts/types';
import { SavedPage } from './SavedPage';
import * as savesApi from '@/api/saves';
import i18n from '@/i18n';
import { resetLanguage, visibleText } from '@/test/i18nHelpers';

vi.mock('@/api/saves', () => ({ listSaved: vi.fn(), toggleSave: vi.fn() }));
vi.mock('@/api/votes', () => ({ castVote: vi.fn() }));

const removedComment: Comment = {
  id: 7,
  post: 3,
  author: null,
  author_username: null,
  author_avatar: null,
  parent: null,
  body: '[removed]',
  body_html: '<p>[removed]</p>',
  is_deleted: true,
  score: 0,
  user_vote: null,
  is_saved: true,
  created_at: '2026-10-01T00:00:00Z',
  updated_at: '2026-10-01T00:00:00Z',
  edited_at: null,
};

const deletedPost = {
  id: 3,
  author: null,
  author_username: null,
  community: 'py',
  flair: null,
  flair_detail: null,
  kind: 'text',
  title: 'Merhaba',
  body: '[deleted]',
  body_html: '<p>[deleted]</p>',
  is_deleted: true,
  url: '',
  image: null,
  is_nsfw: false,
  is_pinned: false,
  is_approved: true,
  score: 0,
  comment_count: 0,
  user_vote: null,
  is_saved: true,
  poll: null,
  created_at: '2026-10-01T00:00:00Z',
  edited_at: null,
} as unknown as Post;

describe('SavedPage in Turkish', () => {
  afterEach(resetLanguage);

  // Saved items stay listed after deletion, so the API's English body markers reach this page.
  it('shows deleted and removed saved items in Turkish', async () => {
    vi.mocked(savesApi.listSaved).mockResolvedValue({
      count: 2,
      next: null,
      previous: null,
      results: [
        { id: 1, target_type: 'comment', object_id: 7, target: removedComment, created_at: '2026-10-02T00:00:00Z' },
        { id: 2, target_type: 'post', object_id: 3, target: deletedPost, created_at: '2026-10-02T00:00:00Z' },
      ],
    });
    await i18n.changeLanguage('tr');
    render(
      <Provider store={configureStore({ reducer: { auth: authReducer } })}>
        <MemoryRouter>
          <SavedPage />
        </MemoryRouter>
      </Provider>,
    );
    expect(await screen.findByText('[kaldırıldı]')).toBeInTheDocument();
    expect(screen.getByText('Merhaba')).toBeInTheDocument();
    expect(visibleText()).not.toMatch(/\[(deleted|removed)\]/);
  });
});

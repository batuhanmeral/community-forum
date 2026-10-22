import { afterEach, describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer, { setUser } from '@/features/auth/authSlice';
import type { Post } from '@/features/posts/types';
import { PostDetailPage } from './PostDetailPage';
import * as postsApi from '@/api/posts';
import * as communitiesApi from '@/api/communities';
import * as commentsApi from '@/api/comments';
import i18n from '@/i18n';
import { resetLanguage, visibleText } from '@/test/i18nHelpers';

vi.mock('@/api/posts', () => ({
  getPost: vi.fn(),
  deletePost: vi.fn(),
  setPostSticky: vi.fn(),
  updatePost: vi.fn(),
  listPostRevisions: vi.fn(),
}));
vi.mock('@/api/communities', () => ({ getCommunity: vi.fn() }));
vi.mock('@/api/comments', () => ({
  listComments: vi.fn(),
  createComment: vi.fn(),
  listCommentRevisions: vi.fn(),
}));
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

describe('PostDetailPage pending banner', () => {
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

  it('tells the author a held post awaits approval', async () => {
    vi.mocked(postsApi.getPost).mockResolvedValue({ ...basePost, is_approved: false });
    renderPage();
    expect(await screen.findByText(/awaiting moderator approval/i)).toBeInTheDocument();
  });

  it('shows no banner on an approved post', async () => {
    vi.mocked(postsApi.getPost).mockResolvedValue(basePost);
    renderPage();
    await screen.findByText('Title');
    expect(screen.queryByText(/awaiting moderator approval/i)).not.toBeInTheDocument();
  });
});

describe('PostDetailPage edit history', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(commentsApi.listComments).mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    });
    vi.mocked(communitiesApi.getCommunity).mockRejectedValue(new Error('skip'));
    vi.mocked(postsApi.listPostRevisions).mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    });
  });

  it('lets the author open the history of an edited post', async () => {
    vi.mocked(postsApi.getPost).mockResolvedValue({
      ...basePost,
      author: 1,
      edited_at: '2026-10-02T00:00:00Z',
    });
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: '(edited)' }));
    expect(await screen.findByText('Edit history')).toBeInTheDocument();
    expect(postsApi.listPostRevisions).toHaveBeenCalledWith(5, 1);
  });

  it('shows a plain marker to other readers', async () => {
    vi.mocked(postsApi.getPost).mockResolvedValue({ ...basePost, edited_at: '2026-10-02T00:00:00Z' });
    renderPage();
    expect(await screen.findByText('(edited)')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '(edited)' })).not.toBeInTheDocument();
  });

  it('hides the history button on a deleted post even for moderators', async () => {
    vi.mocked(communitiesApi.getCommunity).mockResolvedValue({ my_role: 'moderator' } as never);
    vi.mocked(postsApi.getPost).mockResolvedValue({
      ...basePost,
      is_deleted: true,
      edited_at: '2026-10-02T00:00:00Z',
    });
    renderPage();
    expect(await screen.findByText('(edited)')).toBeInTheDocument();
    await waitFor(() => expect(communitiesApi.getCommunity).toHaveBeenCalled());
    expect(screen.queryByRole('button', { name: '(edited)' })).not.toBeInTheDocument();
  });
});

describe('PostDetailPage NSFW image', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(commentsApi.listComments).mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    vi.mocked(communitiesApi.getCommunity).mockRejectedValue(new Error('skip'));
  });

  it('reveals an NSFW image on tap', async () => {
    const user = userEvent.setup();
    vi.mocked(postsApi.getPost).mockResolvedValue({
      ...basePost,
      kind: 'image',
      image: 'https://example.com/i.png',
      is_nsfw: true,
    });
    renderPage();
    await user.click(await screen.findByRole('button', { name: 'Show NSFW content' }));
    expect(screen.queryByRole('button', { name: 'Show NSFW content' })).toBeNull();
    expect(screen.getByAltText('Title').closest('[aria-hidden="true"]')).toBeNull();
  });
});

describe('PostDetailPage in Turkish', () => {
  const ENGLISH_PROBE =
    /\b(Loading|Post not found|removed|Pinned|Unpin|Pin|Report|Edit|Delete|Remove|Cancel|Save|Title|Body|undone)\b/;

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(commentsApi.listComments).mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    vi.mocked(communitiesApi.getCommunity).mockRejectedValue(new Error('skip'));
  });
  afterEach(resetLanguage);

  it('renders no English in Turkish for a moderator and the delete dialog', async () => {
    vi.mocked(communitiesApi.getCommunity).mockResolvedValue({ my_role: 'moderator' } as never);
    vi.mocked(postsApi.getPost).mockResolvedValue({ ...basePost, title: 'Merhaba', is_pinned: true });
    await i18n.changeLanguage('tr');
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: 'Kaldır' }));
    expect(await screen.findByText(/geri alınamaz/)).toBeInTheDocument();
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
  });

  it('renders no English in Turkish for the author edit form', async () => {
    vi.mocked(postsApi.getPost).mockResolvedValue({ ...basePost, author: 1 });
    await i18n.changeLanguage('tr');
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: 'Düzenle' }));
    expect(await screen.findByLabelText('Başlık')).toBeInTheDocument();
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
  });

  it('renders no English in Turkish for a missing post', async () => {
    vi.mocked(postsApi.getPost).mockRejectedValue(new Error('404'));
    await i18n.changeLanguage('tr');
    renderPage();
    expect(await screen.findByText('Gönderi bulunamadı')).toBeInTheDocument();
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
  });

  it('shows the loading text in Turkish', async () => {
    vi.mocked(postsApi.getPost).mockReturnValue(new Promise(() => undefined));
    await i18n.changeLanguage('tr');
    renderPage();
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
    expect(screen.getByText('Yükleniyor…')).toBeInTheDocument();
  });
});

describe('PostDetailPage title', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(commentsApi.listComments).mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    vi.mocked(communitiesApi.getCommunity).mockRejectedValue(new Error('skip'));
  });

  it('sets the page title to the post title', async () => {
    vi.mocked(postsApi.getPost).mockResolvedValue({ ...basePost, title: 'Hello world' });
    renderPage();
    await waitFor(() => expect(document.title).toBe('Hello world · Nexus'));
  });
});

describe('PostDetailPage action row', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(commentsApi.listComments).mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    vi.mocked(communitiesApi.getCommunity).mockResolvedValue({ my_role: 'moderator' } as never);
  });

  // jsdom cannot measure layout; the 360 px overflow check lives in the smoke run.
  it('lets the vote, save and moderator buttons wrap on narrow screens', async () => {
    vi.mocked(postsApi.getPost).mockResolvedValue({ ...basePost, author: 1 });
    renderPage();
    const actions = (await screen.findByRole('button', { name: 'Edit' })).parentElement!;
    expect(actions).toHaveClass('flex-wrap');
    expect(actions.parentElement).toHaveClass('flex-wrap');
  });
});

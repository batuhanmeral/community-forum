import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer from '@/features/auth/authSlice';
import type { Comment } from '@/features/comments/types';
import { CommentSection } from './CommentSection';
import * as commentsApi from '@/api/comments';
import i18n from '@/i18n';
import { resetLanguage, visibleText } from '@/test/i18nHelpers';
import { setUser } from '@/features/auth/authSlice';

vi.mock('@/api/comments', () => ({
  listComments: vi.fn(),
  createComment: vi.fn(),
  updateComment: vi.fn(),
  deleteComment: vi.fn(),
  listCommentRevisions: vi.fn(),
}));

const listComments = vi.mocked(commentsApi.listComments);

function comment(id: number, parent: number | null = null): Comment {
  return {
    id,
    post: 1,
    author: 2,
    author_username: 'bob',
    parent,
    body: `body ${id}`,
    body_html: `<p>body ${id}</p>`,
    is_deleted: false,
    score: 0,
    user_vote: null,
    is_saved: false,
    created_at: '2026-10-01T00:00:00Z',
    updated_at: '2026-10-01T00:00:00Z',
    edited_at: null,
  };
}

function renderSection(path = '/posts/1', isModerator = false) {
  const store = configureStore({ reducer: { auth: authReducer } });
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={[path]}>
        <CommentSection postId={1} isModerator={isModerator} />
      </MemoryRouter>
    </Provider>,
  );
}

beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

describe('CommentSection', () => {
  beforeEach(() => vi.clearAllMocks());

  it('shows the server total, not the loaded length', async () => {
    listComments.mockResolvedValue({ count: 501, next: 'p2', previous: null, results: [comment(1)] });
    renderSection();
    expect(await screen.findByText('501 comments')).toBeInTheDocument();
  });

  it('loads the next page on demand and appends it', async () => {
    listComments
      .mockResolvedValueOnce({ count: 2, next: 'p2', previous: null, results: [comment(1)] })
      .mockResolvedValueOnce({ count: 2, next: null, previous: 'p1', results: [comment(2, 1)] });
    renderSection();
    await userEvent.click(await screen.findByRole('button', { name: 'Load more comments' }));
    expect(await screen.findByText('body 2')).toBeInTheDocument();
    expect(listComments).toHaveBeenLastCalledWith(1, { sort: 'best', page: 2 });
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: 'Load more comments' })).not.toBeInTheDocument(),
    );
  });
  it('renders a comment once when the next page repeats it', async () => {
    listComments
      .mockResolvedValueOnce({ count: 3, next: 'p2', previous: null, results: [comment(1), comment(2)] })
      .mockResolvedValueOnce({ count: 3, next: null, previous: 'p1', results: [comment(2), comment(3)] });
    renderSection();
    await userEvent.click(await screen.findByRole('button', { name: 'Load more comments' }));
    expect(await screen.findByText('body 3')).toBeInTheDocument();
    expect(screen.getAllByText('body 2')).toHaveLength(1);
  });

  it('shows an inline error when loading more fails and keeps the button', async () => {
    listComments
      .mockResolvedValueOnce({ count: 2, next: 'p2', previous: null, results: [comment(1)] })
      .mockRejectedValueOnce(new Error('boom'));
    renderSection();
    await userEvent.click(await screen.findByRole('button', { name: 'Load more comments' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load more comments.');
    expect(screen.getByRole('button', { name: 'Load more comments' })).toBeInTheDocument();
  });

  it('drops a load-more page that resolves after the sort changed', async () => {
    let resolveStale: (v: Awaited<ReturnType<typeof commentsApi.listComments>>) => void = () => {};
    listComments
      .mockResolvedValueOnce({ count: 2, next: 'p2', previous: null, results: [comment(1)] })
      .mockReturnValueOnce(new Promise((resolve) => (resolveStale = resolve)))
      .mockResolvedValueOnce({ count: 1, next: null, previous: null, results: [comment(3)] });
    renderSection();
    await userEvent.click(await screen.findByRole('button', { name: 'Load more comments' }));
    await userEvent.selectOptions(screen.getByRole('combobox'), 'new');
    expect(await screen.findByText('body 3')).toBeInTheDocument();
    resolveStale({ count: 2, next: 'p3', previous: 'p1', results: [comment(2)] });
    await waitFor(() => expect(screen.queryByText('body 2')).not.toBeInTheDocument());
    expect(screen.queryByRole('button', { name: 'Load more comments' })).not.toBeInTheDocument();
  });

  it('scrolls to the comment named in the URL hash', async () => {
    listComments.mockResolvedValue({ count: 1, next: null, previous: null, results: [comment(5)] });
    renderSection('/posts/1#comment-5');
    await screen.findByText('body 5');
    await waitFor(() => expect(Element.prototype.scrollIntoView).toHaveBeenCalled());
  });

  it('scrolls once per hash, not again when the sort changes', async () => {
    listComments.mockResolvedValue({ count: 1, next: null, previous: null, results: [comment(5)] });
    renderSection('/posts/1#comment-5');
    await screen.findByText('body 5');
    await waitFor(() => expect(Element.prototype.scrollIntoView).toHaveBeenCalledTimes(1));
    await userEvent.selectOptions(screen.getByRole('combobox'), 'new');
    await waitFor(() => expect(listComments).toHaveBeenCalledTimes(2));
    await screen.findByText('body 5');
    await waitFor(() => expect(screen.queryByText('Loading comments…')).not.toBeInTheDocument());
    expect(Element.prototype.scrollIntoView).toHaveBeenCalledTimes(1);
  });

  it('lets a moderator open the history of an edited comment', async () => {
    const edited = { ...comment(1), edited_at: '2026-10-02T00:00:00Z' };
    listComments.mockResolvedValue({ count: 1, next: null, previous: null, results: [edited] });
    vi.mocked(commentsApi.listCommentRevisions).mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    });
    renderSection('/posts/1', true);
    await userEvent.click(await screen.findByRole('button', { name: '(edited)' }));
    expect(await screen.findByText('Edit history')).toBeInTheDocument();
    expect(commentsApi.listCommentRevisions).toHaveBeenCalledWith(1, 1);
  });

  it('shows a plain marker to readers who are neither author nor moderator', async () => {
    const edited = { ...comment(1), edited_at: '2026-10-02T00:00:00Z' };
    listComments.mockResolvedValue({ count: 1, next: null, previous: null, results: [edited] });
    renderSection();
    expect(await screen.findByText('(edited)')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '(edited)' })).not.toBeInTheDocument();
  });

  it('hides the history button on a deleted comment even for moderators', async () => {
    const deleted = { ...comment(1), is_deleted: true, edited_at: '2026-10-02T00:00:00Z' };
    listComments.mockResolvedValue({ count: 1, next: null, previous: null, results: [deleted] });
    renderSection('/posts/1', true);
    expect(await screen.findByText('(edited)')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '(edited)' })).not.toBeInTheDocument();
  });
});

describe('CommentSection in Turkish', () => {
  const ENGLISH_PROBE =
    /\b(Best|Top|New|Old|Controversial|Log in|Add a comment|Reply|Report|Edit|Delete|Save|Saved|Cancel|Comment|Loading|No comments|more repl(?:y|ies)|Collapse|Expand|Upvote|Downvote)\b/;

  beforeEach(() => vi.clearAllMocks());
  afterEach(resetLanguage);

  function renderAs(userId: number | null) {
    const store = configureStore({ reducer: { auth: authReducer } });
    if (userId !== null) {
      store.dispatch(
        setUser({
          id: userId,
          username: 'bob',
          email: 'b@x.com',
          email_verified: true,
          avatar: null,
          bio: '',
          show_nsfw: false,
          post_karma: 0,
          comment_karma: 0,
        }),
      );
    }
    return render(
      <Provider store={store}>
        <MemoryRouter initialEntries={['/posts/1']}>
          <CommentSection postId={1} />
        </MemoryRouter>
      </Provider>,
    );
  }

  it('renders no English in Turkish while loading and when empty', async () => {
    await i18n.changeLanguage('tr');
    listComments.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    renderAs(null);
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
    await screen.findByText(/Henüz yorum yok/);
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
  });

  it('renders no English in Turkish for a signed-out reader', async () => {
    await i18n.changeLanguage('tr');
    listComments.mockResolvedValue({ count: 2, next: null, previous: null, results: [comment(1), comment(2, 1)] });
    renderAs(null);
    await screen.findByText('body 1');
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
  });

  it('renders no English in Turkish for the author with the reply and edit forms open', async () => {
    await i18n.changeLanguage('tr');
    listComments.mockResolvedValue({ count: 2, next: null, previous: null, results: [comment(1), comment(2, 1)] });
    renderAs(2);
    await screen.findByText('body 1');
    const buttons = (name: string) => screen.getAllByRole('button', { name: i18n.t(name) });
    await userEvent.click(buttons('common.reply')[0]);
    await userEvent.click(buttons('common.edit')[0]);
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
    await userEvent.click(screen.getAllByRole('button', { name: i18n.t('comments.collapse') })[0]);
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
  });
});
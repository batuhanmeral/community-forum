import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer from '@/features/auth/authSlice';
import { FollowListModal } from './FollowListModal';
import * as followApi from '@/api/follow';
import i18n from '@/i18n';
import { resetLanguage, visibleText } from '@/test/i18nHelpers';

vi.mock('@/api/follow', () => ({
  listFollowers: vi.fn(),
  listFollowing: vi.fn(),
  followUser: vi.fn(),
  unfollowUser: vi.fn(),
}));

const api = vi.mocked(followApi);
const user = (id: number) => ({ id, username: `user${id}`, avatar: null, is_following: false });

describe('FollowListModal', () => {
  beforeEach(() => vi.clearAllMocks());

  it('reports a failed load-more and keeps the list and button', async () => {
    api.listFollowers
      .mockResolvedValueOnce({ count: 2, next: 'p2', previous: null, results: [user(1)] })
      .mockRejectedValueOnce(new Error('down'));
    render(
      <Provider store={configureStore({ reducer: { auth: authReducer } })}>
        <MemoryRouter>
          <FollowListModal open onClose={() => {}} username="bob" mode="followers" />
        </MemoryRouter>
      </Provider>,
    );
    await userEvent.click(await screen.findByRole('button', { name: 'Load more' }));
    expect(await screen.findByText('Could not load more people.')).toBeInTheDocument();
    expect(screen.getByText('u/user1')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Load more' })).toBeEnabled();
  });
});

describe('FollowListModal in Turkish', () => {
  const ENGLISH_PROBE = /\b(followers?|following|Follow|Loading|Load more|No followers|Not following|is following)\b/;

  beforeEach(() => vi.clearAllMocks());
  afterEach(resetLanguage);

  function renderModal(mode: 'followers' | 'following') {
    return render(
      <Provider store={configureStore({ reducer: { auth: authReducer } })}>
        <MemoryRouter>
          <FollowListModal open onClose={() => {}} username="bob" mode={mode} />
        </MemoryRouter>
      </Provider>,
    );
  }

  it.each(['followers', 'following'] as const)('renders no English in Turkish for %s', async (mode) => {
    await i18n.changeLanguage('tr');
    api.listFollowers.mockResolvedValue({ count: 1, next: 'p2', previous: null, results: [user(1)] });
    api.listFollowing.mockResolvedValue({ count: 1, next: 'p2', previous: null, results: [user(1)] });
    renderModal(mode);
    await screen.findByText('u/user1');
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
  });

  it('renders no English in Turkish while loading', async () => {
    await i18n.changeLanguage('tr');
    api.listFollowers.mockReturnValue(new Promise(() => undefined));
    renderModal('followers');
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
  });

  it.each(['followers', 'following'] as const)('renders no English in Turkish for an empty %s list', async (mode) => {
    await i18n.changeLanguage('tr');
    api.listFollowers.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    api.listFollowing.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    renderModal(mode);
    await screen.findByText(i18n.t(mode === 'followers' ? 'follow.noFollowers' : 'follow.noFollowing'));
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
  });
});
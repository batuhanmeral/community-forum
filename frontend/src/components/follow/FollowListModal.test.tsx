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

  const loaded = { count: 1, next: 'p2', previous: null, results: [user(1)] };
  const empty = { count: 0, next: null, previous: null, results: [] };

  it.each([
    ['followers', 'loaded', loaded, (): string => 'u/user1'],
    ['following', 'loaded', loaded, (): string => 'u/user1'],
    ['followers', 'empty', empty, (): string => i18n.t('follow.noFollowers')],
    ['following', 'empty', empty, (): string => i18n.t('follow.noFollowing')],
  ] as const)('renders no English in Turkish for %s (%s)', async (mode, _state, response, textToAwait) => {
    await i18n.changeLanguage('tr');
    api.listFollowers.mockResolvedValue(response);
    api.listFollowing.mockResolvedValue(response);
    renderModal(mode);
    await screen.findByText(textToAwait());
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
  });

  it('renders no English in Turkish while loading', async () => {
    await i18n.changeLanguage('tr');
    api.listFollowers.mockReturnValue(new Promise(() => undefined));
    renderModal('followers');
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
  });
});

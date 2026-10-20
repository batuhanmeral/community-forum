import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer from '@/features/auth/authSlice';
import { FollowListModal } from './FollowListModal';
import * as followApi from '@/api/follow';

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

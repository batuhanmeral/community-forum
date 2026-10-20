import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, render, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer, { logout, setUser } from '@/features/auth/authSlice';
import membershipsReducer, { membershipsChanged } from '@/features/communities/membershipsSlice';
import { Sidebar } from './Sidebar';
import * as communitiesApi from '@/api/communities';
import type { Community } from '@/features/communities/types';

vi.mock('@/api/communities', () => ({ listCommunities: vi.fn() }));

function renderSidebar() {
  const store = configureStore({
    reducer: { auth: authReducer, memberships: membershipsReducer },
  });
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
  render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/']}>
        <Sidebar />
      </MemoryRouter>
    </Provider>,
  );
  return store;
}

describe('Sidebar joined communities', () => {
  beforeEach(() => {
    vi.mocked(communitiesApi.listCommunities).mockReset();
    vi.mocked(communitiesApi.listCommunities).mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    });
  });

  it('does not refetch joined communities on route changes', async () => {
    renderSidebar();
    await waitFor(() => expect(communitiesApi.listCommunities).toHaveBeenCalledTimes(1));

    const user = userEvent.setup();
    await user.click(document.querySelector('a[href="/popular"]')!);
    await user.click(document.querySelector('a[href="/saved"]')!);

    expect(communitiesApi.listCommunities).toHaveBeenCalledTimes(1);
  });

  it('refetches after membershipsChanged', async () => {
    const store = renderSidebar();
    await waitFor(() => expect(communitiesApi.listCommunities).toHaveBeenCalledTimes(1));

    act(() => {
      store.dispatch(membershipsChanged());
    });

    await waitFor(() => expect(communitiesApi.listCommunities).toHaveBeenCalledTimes(2));
  });

  it('ignores a joined-communities response after logout', async () => {
    let resolve!: (page: { count: number; next: null; previous: null; results: Community[] }) => void;
    vi.mocked(communitiesApi.listCommunities).mockReturnValue(new Promise((r) => (resolve = r)));
    const store = renderSidebar();
    await waitFor(() => expect(communitiesApi.listCommunities).toHaveBeenCalledTimes(1));
    act(() => {
      store.dispatch(logout());
    });
    const cats = { id: 7, slug: 'cats', member_count: 3 } as Community;
    await act(async () => resolve({ count: 1, next: null, previous: null, results: [cats] }));
    expect(document.querySelector('a[href="/c/cats"]')).toBeNull();
  });

  it('clears the joined communities on logout', async () => {
    const cats = { id: 7, slug: 'cats', member_count: 3 } as Community;
    vi.mocked(communitiesApi.listCommunities).mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [cats],
    });
    const store = renderSidebar();
    await waitFor(() => expect(document.querySelector('a[href="/c/cats"]')).not.toBeNull());
    act(() => {
      store.dispatch(logout());
    });
    expect(document.querySelector('a[href="/c/cats"]')).toBeNull();
  });
});

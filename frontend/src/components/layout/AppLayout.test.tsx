import { useEffect } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, useNavigate, type NavigateFunction } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer, { logout, setTokens, syncFromStorage } from '@/features/auth/authSlice';
import type { User } from '@/features/auth/types';
import * as authApi from '@/api/auth';
import { fakeJwt } from '@/test/fakeJwt';
import { AppLayout } from './AppLayout';

vi.mock('@/api/auth', () => ({ fetchMe: vi.fn() }));
vi.mock('./Navbar', () => ({
  Navbar: ({ onOpenMenu }: { onOpenMenu?: () => void }) => (
    <button type="button" onClick={onOpenMenu}>
      Open menu
    </button>
  ),
}));
vi.mock('./Sidebar', () => ({ Sidebar: () => null, SidebarNav: () => null }));
vi.mock('./HomeRightSidebar', () => ({ HomeRightSidebar: () => null }));

const fetchMe = vi.mocked(authApi.fetchMe);
const ALICE_ACCESS = fakeJwt({ user_id: 1 });

const alice: User = {
  id: 1,
  username: 'alice',
  email: 'a@x.com',
  email_verified: true,
  avatar: null,
  bio: '',
  show_nsfw: false,
  post_karma: 0,
  comment_karma: 0,
};

let navigateTo!: NavigateFunction;
function NavigateProbe() {
  const navigate = useNavigate();
  useEffect(() => {
    navigateTo = navigate;
  }, [navigate]);
  return null;
}

function renderLayout() {
  const store = configureStore({ reducer: { auth: authReducer } });
  store.dispatch(setTokens({ access: ALICE_ACCESS, refresh: 'r1' }));
  render(
    <Provider store={store}>
      <MemoryRouter>
        <AppLayout />
        <NavigateProbe />
      </MemoryRouter>
    </Provider>,
  );
  return store;
}

describe('AppLayout session loading', () => {
  beforeEach(() => {
    localStorage.clear();
    fetchMe.mockReset();
  });

  it('keeps tokens when fetchMe fails', async () => {
    fetchMe.mockRejectedValue(new Error('Network Error'));
    const store = renderLayout();
    await waitFor(() => expect(fetchMe).toHaveBeenCalledTimes(1));
    await act(async () => {});
    expect(store.getState().auth.refreshToken).toBe('r1');
    expect(store.getState().auth.accessToken).toBe(ALICE_ACCESS);
  });

  it('drops a /users/me/ response that arrives after logout', async () => {
    let resolve!: (user: User) => void;
    fetchMe.mockReturnValue(new Promise((r) => (resolve = r)));
    const store = renderLayout();
    await waitFor(() => expect(fetchMe).toHaveBeenCalledTimes(1));
    act(() => {
      store.dispatch(logout());
    });
    await act(async () => resolve(alice));
    expect(store.getState().auth.user).toBeNull();
    expect(store.getState().auth.status).toBe('idle');
  });

  it("drops the previous account's /users/me/ response after a switch", async () => {
    const bob: User = { ...alice, id: 99, username: 'bob' };
    const pending: Array<(user: User) => void> = [];
    fetchMe.mockImplementation(() => new Promise((r) => pending.push(r)));
    const store = renderLayout();
    await waitFor(() => expect(fetchMe).toHaveBeenCalledTimes(1));
    act(() => {
      store.dispatch(syncFromStorage({ access: fakeJwt({ user_id: 99 }), refresh: 'r9' }));
    });
    await waitFor(() => expect(fetchMe).toHaveBeenCalledTimes(2));
    await act(async () => pending[0](alice));
    expect(store.getState().auth.user).toBeNull();
    await act(async () => pending[1](bob));
    expect(store.getState().auth.user).toEqual(bob);
  });

  it('retries fetchMe when the browser comes back online', async () => {
    fetchMe.mockRejectedValueOnce(new Error('Network Error')).mockResolvedValue(alice);
    const store = renderLayout();
    await waitFor(() => expect(fetchMe).toHaveBeenCalledTimes(1));
    await act(async () => {});
    await act(async () => {
      window.dispatchEvent(new Event('online'));
    });
    expect(fetchMe).toHaveBeenCalledTimes(2);
    await waitFor(() => expect(store.getState().auth.user).toEqual(alice));
  });
});

describe('AppLayout mobile drawer', () => {
  beforeEach(() => {
    localStorage.clear();
    fetchMe.mockReset();
    fetchMe.mockResolvedValue(alice);
  });

  it('the menu button opens the drawer', async () => {
    renderLayout();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole('button', { name: 'Open menu' }));
    expect(screen.getByRole('dialog', { name: 'Menu' })).toHaveAttribute('open');
  });

  it('closes on route change', async () => {
    renderLayout();
    await userEvent.setup().click(screen.getByRole('button', { name: 'Open menu' }));
    const dialog = screen.getByRole('dialog', { name: 'Menu' });
    await act(async () => {
      await navigateTo('/popular');
    });
    expect(dialog).not.toHaveAttribute('open');
  });
});

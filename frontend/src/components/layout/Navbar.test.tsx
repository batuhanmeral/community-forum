import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer, { REFRESH_KEY, logout, setUser } from '@/features/auth/authSlice';
import messagingReducer from '@/features/messaging/messagingSlice';
import notificationReducer from '@/features/notifications/notificationSlice';
import { Navbar } from './Navbar';
import * as usersApi from '@/api/users';
import * as messagingApi from '@/api/messaging';
import * as notificationsApi from '@/api/notifications';
import * as authApi from '@/api/auth';

vi.mock('@/api/users', () => ({ getUnreadCounts: vi.fn() }));
vi.mock('@/api/messaging', () => ({ listConversations: vi.fn() }));
vi.mock('@/api/notifications', () => ({ listNotifications: vi.fn() }));
vi.mock('@/api/auth', () => ({ logoutRequest: vi.fn() }));

const users = vi.mocked(usersApi);

function renderNavbar() {
  const store = configureStore({
    reducer: { auth: authReducer, messaging: messagingReducer, notifications: notificationReducer },
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
      <MemoryRouter>
        <Navbar />
      </MemoryRouter>
    </Provider>,
  );
  return store;
}

function setHidden(hidden: boolean) {
  Object.defineProperty(document, 'hidden', { configurable: true, value: hidden });
}

describe('Navbar unread badges', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    users.getUnreadCounts.mockResolvedValue({ notifications: 5, messages: 3 });
  });

  afterEach(() => {
    setHidden(false);
    vi.useRealTimers();
  });

  it('polls only the unread-counts endpoint and fills both badges', async () => {
    const store = renderNavbar();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(store.getState().messaging.dmUnreadCount).toBe(3);
    expect(store.getState().notifications.unreadCount).toBe(5);
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();

    users.getUnreadCounts.mockResolvedValue({ notifications: 6, messages: 4 });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(store.getState().messaging.dmUnreadCount).toBe(4);
    expect(store.getState().notifications.unreadCount).toBe(6);
    expect(users.getUnreadCounts).toHaveBeenCalledTimes(2);
    expect(vi.mocked(messagingApi.listConversations)).not.toHaveBeenCalled();
    expect(vi.mocked(notificationsApi.listNotifications)).not.toHaveBeenCalled();
  });

  it('skips polls while the tab is hidden and refetches when it becomes visible', async () => {
    renderNavbar();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(users.getUnreadCounts).toHaveBeenCalledTimes(1);

    setHidden(true);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(90_000);
    });
    expect(users.getUnreadCounts).toHaveBeenCalledTimes(1);

    setHidden(false);
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'));
    });
    expect(users.getUnreadCounts).toHaveBeenCalledTimes(2);
  });

  it('keeps the last badge values when a poll fails', async () => {
    const store = renderNavbar();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    users.getUnreadCounts.mockRejectedValue(new Error('down'));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(store.getState().messaging.dmUnreadCount).toBe(3);
    expect(store.getState().notifications.unreadCount).toBe(5);
  });

  it('clears both badges on logout', async () => {
    const store = renderNavbar();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(store.getState().notifications.unreadCount).toBe(5);
    act(() => {
      store.dispatch(logout());
    });
    expect(store.getState().messaging.dmUnreadCount).toBe(0);
    expect(store.getState().notifications.unreadCount).toBe(0);
  });

  it('ignores unread counts that arrive after logout', async () => {
    let resolve!: (counts: { notifications: number; messages: number }) => void;
    users.getUnreadCounts.mockReturnValue(
      new Promise((r) => {
        resolve = r;
      }),
    );
    const store = renderNavbar();
    expect(users.getUnreadCounts).toHaveBeenCalledTimes(1);
    act(() => {
      store.dispatch(logout());
    });
    await act(async () => {
      resolve({ notifications: 5, messages: 3 });
    });
    expect(store.getState().messaging.dmUnreadCount).toBe(0);
    expect(store.getState().notifications.unreadCount).toBe(0);
  });
});

describe('Navbar logout', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    users.getUnreadCounts.mockResolvedValue({ notifications: 0, messages: 0 });
  });

  it('logs out under the refresh lock with the refresh token in storage', async () => {
    const request = vi.fn((_name: string, fn: () => Promise<unknown>) => fn());
    Object.defineProperty(navigator, 'locks', { configurable: true, value: { request } });
    try {
      const store = renderNavbar();
      localStorage.setItem(REFRESH_KEY, 'r2'); // rotated by a refresh; the store never held it
      fireEvent.click(screen.getByRole('button', { name: 'Profile menu' }));
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: 'Log out' }));
      });
      expect(request).toHaveBeenCalledWith('nexus.auth.refresh', expect.any(Function));
      expect(vi.mocked(authApi.logoutRequest)).toHaveBeenCalledWith('r2');
      expect(store.getState().auth.user).toBeNull();
      expect(localStorage.getItem(REFRESH_KEY)).toBeNull();
    } finally {
      delete (navigator as { locks?: unknown }).locks;
    }
  });
});

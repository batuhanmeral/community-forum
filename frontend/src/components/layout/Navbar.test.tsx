import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer, { setUser } from '@/features/auth/authSlice';
import messagingReducer from '@/features/messaging/messagingSlice';
import notificationReducer from '@/features/notifications/notificationSlice';
import { Navbar } from './Navbar';
import * as usersApi from '@/api/users';
import * as messagingApi from '@/api/messaging';
import * as notificationsApi from '@/api/notifications';

vi.mock('@/api/users', () => ({ getUnreadCounts: vi.fn() }));
vi.mock('@/api/messaging', () => ({ listConversations: vi.fn() }));
vi.mock('@/api/notifications', () => ({ listNotifications: vi.fn() }));

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
});

import type { ComponentProps } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
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
import i18n from '@/i18n';
import { resetLanguage, visibleText } from '@/test/i18nHelpers';

vi.mock('@/api/users', () => ({ getUnreadCounts: vi.fn() }));
vi.mock('@/api/messaging', () => ({ listConversations: vi.fn() }));
vi.mock('@/api/notifications', () => ({ listNotifications: vi.fn() }));
vi.mock('@/api/auth', () => ({ logoutRequest: vi.fn() }));

const users = vi.mocked(usersApi);

function LocationProbe() {
  const { pathname, search } = useLocation();
  return <output data-testid="location">{pathname + search}</output>;
}

function renderNavbar(props: ComponentProps<typeof Navbar> = {}) {
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
        <Navbar {...props} />
        <LocationProbe />
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

describe('Navbar while the profile is loading', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    users.getUnreadCounts.mockResolvedValue({ notifications: 0, messages: 0 });
  });

  // Offering "Log in" to a signed-in user is a dead end: LoginPage sends them straight back.
  it('shows a neutral placeholder instead of log in and sign up', async () => {
    const store = configureStore({
      reducer: { auth: authReducer, messaging: messagingReducer, notifications: notificationReducer },
      preloadedState: {
        auth: { user: null, accessToken: 'a1', refreshToken: 'r1', status: 'authenticated' as const, error: null },
      },
    });
    render(
      <Provider store={store}>
        <MemoryRouter>
          <Navbar />
        </MemoryRouter>
      </Provider>,
    );
    await act(async () => {});
    expect(screen.queryByRole('link', { name: 'Log in' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Sign up' })).not.toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Loading your account…');
  });

  it('still offers log in and sign up when signed out', async () => {
    const store = configureStore({
      reducer: { auth: authReducer, messaging: messagingReducer, notifications: notificationReducer },
    });
    store.dispatch(logout());
    render(
      <Provider store={store}>
        <MemoryRouter>
          <Navbar />
        </MemoryRouter>
      </Provider>,
    );
    expect(screen.getByRole('link', { name: 'Log in' })).toBeInTheDocument();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });
});

describe('Navbar mobile header', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    users.getUnreadCounts.mockResolvedValue({ notifications: 0, messages: 0 });
  });

  it('the mobile search button reveals the search box', async () => {
    renderNavbar();
    await act(async () => {});
    expect(screen.getAllByRole('searchbox')).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: 'Open search' }));
    const boxes = screen.getAllByRole('searchbox');
    expect(boxes).toHaveLength(2);
    expect(boxes[1]).toHaveFocus();
    expect(screen.getByRole('button', { name: 'Open search' })).toHaveAttribute('aria-expanded', 'true');
  });

  it('searches from the mobile search row', async () => {
    renderNavbar();
    await act(async () => {});
    fireEvent.click(screen.getByRole('button', { name: 'Open search' }));
    const box = screen.getAllByRole('searchbox')[1];
    fireEvent.change(box, { target: { value: 'cats' } });
    fireEvent.submit(box.closest('form')!);
    expect(screen.getByTestId('location')).toHaveTextContent('/search?q=cats&type=post');
  });

  it('the menu button asks the layout to open the drawer', async () => {
    const onOpenMenu = vi.fn();
    renderNavbar({ onOpenMenu });
    await act(async () => {});
    fireEvent.click(screen.getByRole('button', { name: 'Open menu' }));
    expect(onOpenMenu).toHaveBeenCalledTimes(1);
  });
});

describe('Navbar in Turkish', () => {
  const ENGLISH_PROBE = /\b(Hide|Show|Search|Profile menu|Notifications|Menu|Messages|Post)\b/;

  afterEach(resetLanguage);

  it('renders no English in Turkish', async () => {
    users.getUnreadCounts.mockResolvedValue({ notifications: 0, messages: 0 });
    await i18n.changeLanguage('tr');
    renderNavbar({ onToggleLeft: vi.fn(), onToggleRight: vi.fn(), onOpenMenu: vi.fn(), leftOpen: true, rightOpen: false });
    await act(async () => {});
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
  });
});
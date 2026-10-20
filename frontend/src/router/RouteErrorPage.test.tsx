import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RouterProvider, createMemoryRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer from '@/features/auth/authSlice';
import membershipsReducer from '@/features/communities/membershipsSlice';
import messagingReducer from '@/features/messaging/messagingSlice';
import notificationReducer from '@/features/notifications/notificationSlice';
import { CHUNK_RELOAD_KEY, RouteErrorPage } from './RouteErrorPage';
import { routes } from './index';

vi.mock('@/api/users', () => ({
  getUnreadCounts: vi.fn().mockResolvedValue({ notifications: 0, messages: 0 }),
  getLeaderboard: vi.fn().mockResolvedValue([]),
}));
vi.mock('@/api/messaging', () => ({ listConversations: vi.fn().mockResolvedValue([]) }));
vi.mock('@/api/notifications', () => ({ listNotifications: vi.fn().mockResolvedValue([]) }));
vi.mock('@/api/communities', () => ({
  listCommunities: vi.fn().mockResolvedValue([]),
  joinCommunity: vi.fn(),
  leaveCommunity: vi.fn(),
}));
vi.mock('@/api/trending', () => ({
  trendingCommunities: vi.fn().mockResolvedValue([]),
  trendingPosts: vi.fn().mockResolvedValue([]),
}));

let thrown: unknown;
vi.mock('./pages', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./pages')>()),
  HomePage: () => {
    throw thrown;
  },
}));

const reload = vi.fn();
let consoleError: ReturnType<typeof vi.spyOn>;
const originalLocation = window.location;

function renderWith(router: ReturnType<typeof createMemoryRouter>) {
  const store = configureStore({
    reducer: {
      auth: authReducer,
      memberships: membershipsReducer,
      messaging: messagingReducer,
      notifications: notificationReducer,
    },
  });
  render(
    <Provider store={store}>
      <RouterProvider router={router} />
    </Provider>,
  );
}

function renderThrowing(error: unknown) {
  thrown = error;
  const Boom = () => {
    throw error;
  };
  renderWith(
    createMemoryRouter([{ path: '/', element: <Boom />, errorElement: <RouteErrorPage /> }]),
  );
}

describe('RouteErrorPage', () => {
  beforeEach(() => {
    reload.mockClear();
    sessionStorage.clear();
    vi.stubGlobal('location', { ...originalLocation, reload });
    consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    consoleError.mockRestore();
  });

  it('reloads once on a dynamic-import failure', () => {
    renderThrowing(new TypeError('Failed to fetch dynamically imported module: /assets/x.js'));
    expect(reload).toHaveBeenCalledTimes(1);
    expect(Number(sessionStorage.getItem(CHUNK_RELOAD_KEY))).toBeGreaterThan(0);
  });

  it('does not reload twice within the cooldown', () => {
    sessionStorage.setItem(CHUNK_RELOAD_KEY, String(Date.now() - 1_000));
    renderThrowing(new TypeError('Importing a module script failed.'));
    expect(reload).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument();
  });

  it('shows the error screen without reloading for other errors', () => {
    renderThrowing(new Error('boom'));
    expect(reload).not.toHaveBeenCalled();
    expect(screen.getByRole('heading', { name: 'Something went wrong' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Go home' })).toHaveAttribute('href', '/');
  });

  it('keeps the navbar when a page inside the layout fails', () => {
    thrown = new Error('boom');
    renderWith(createMemoryRouter(routes, { initialEntries: ['/'] }));
    expect(screen.getByRole('banner')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Something went wrong' })).toBeInTheDocument();
  });
});

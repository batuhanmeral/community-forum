import { describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import notificationReducer from '@/features/notifications/notificationSlice';
import * as notificationsApi from '@/api/notifications';
import { NotificationDropdown } from './NotificationDropdown';

vi.mock('@/api/notifications', () => ({
  listNotifications: vi.fn(),
  markNotificationRead: vi.fn(),
  markAllNotificationsRead: vi.fn(),
}));

describe('NotificationDropdown', () => {
  it('the notification panel is pinned inside the viewport on small screens', async () => {
    vi.mocked(notificationsApi.listNotifications).mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    });
    const store = configureStore({ reducer: { notifications: notificationReducer } });
    render(
      <Provider store={store}>
        <MemoryRouter>
          <NotificationDropdown unreadCount={0} />
        </MemoryRouter>
      </Provider>,
    );
    const bell = screen.getByRole('button', { name: 'Notifications' });
    await act(async () => {
      fireEvent.click(bell);
    });
    // jsdom has no layout, so pin the class contract: fixed with an 8 px gutter below 640 px, 360 px only from sm up.
    const classes = (bell.nextElementSibling as HTMLElement).className.split(/\s+/);
    expect(classes).toEqual(expect.arrayContaining(['max-sm:fixed', 'max-sm:inset-x-2', 'sm:w-[360px]']));
    expect(classes.some((c) => c.startsWith('max-sm:top-'))).toBe(true);
    expect(classes).not.toContain('w-[360px]');
  });
});

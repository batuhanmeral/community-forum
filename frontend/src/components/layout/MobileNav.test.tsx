import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer, { setUser } from '@/features/auth/authSlice';
import membershipsReducer from '@/features/communities/membershipsSlice';
import * as communitiesApi from '@/api/communities';
import { MobileNav } from './MobileNav';

vi.mock('@/api/communities', () => ({ listCommunities: vi.fn() }));

function renderDrawer(onClose = vi.fn()) {
  const store = configureStore({ reducer: { auth: authReducer, memberships: membershipsReducer } });
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
        <MobileNav open onClose={onClose} />
      </MemoryRouter>
    </Provider>,
  );
  return onClose;
}

describe('MobileNav', () => {
  beforeEach(() => {
    vi.mocked(communitiesApi.listCommunities).mockReset();
    vi.mocked(communitiesApi.listCommunities).mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    });
  });

  it('the drawer lists every destination', async () => {
    renderDrawer();
    const dialog = await screen.findByRole('dialog', { name: 'Menu' });
    expect(dialog).toHaveAttribute('open');
    for (const name of ['Home', 'Popular', 'All', 'Saved', 'Browse all', '+ New', 'Settings']) {
      expect(screen.getByRole('link', { name })).toBeInTheDocument();
    }
    expect(screen.getByRole('link', { name: '+ New' })).toHaveAttribute('href', '/c/create');
  });

  it('closes when a link is chosen', async () => {
    const onClose = renderDrawer();
    await userEvent.setup().click(await screen.findByRole('link', { name: 'Popular' }));
    expect(onClose).toHaveBeenCalled();
  });

  it('closes when the dialog is dismissed', async () => {
    const onClose = renderDrawer();
    const dialog = await screen.findByRole('dialog', { name: 'Menu' });
    act(() => {
      (dialog as HTMLDialogElement).close();
    });
    expect(onClose).toHaveBeenCalled();
  });

  it('closes on a backdrop click but not on a click inside the panel', async () => {
    const onClose = renderDrawer();
    const dialog = await screen.findByRole('dialog', { name: 'Menu' });
    fireEvent.pointerDown(screen.getByText('Communities'));
    fireEvent.click(screen.getByText('Communities'));
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.pointerDown(dialog);
    fireEvent.click(dialog);
    expect(onClose).toHaveBeenCalled();
  });

  it('stays open when a drag starts in the panel and ends on the backdrop', async () => {
    const onClose = renderDrawer();
    const dialog = await screen.findByRole('dialog', { name: 'Menu' });
    fireEvent.pointerDown(screen.getByText('Communities'));
    fireEvent.click(dialog);
    expect(onClose).not.toHaveBeenCalled();
  });

  it('stops the page behind from scrolling while open', async () => {
    renderDrawer();
    await screen.findByRole('dialog', { name: 'Menu' });
    expect(document.body.style.overflow).toBe('hidden');
  });
});

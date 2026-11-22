import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { beforeEach, expect, it, vi } from 'vitest';
import '@/i18n';
import authReducer, { setUser } from '@/features/auth/authSlice';
import { ModmailThreadPage } from './ModmailThreadPage';
import * as api from '@/api/modmail';

vi.mock('@/api/modmail');

const messages = {
  count: 2,
  next: null,
  previous: null,
  results: [
    { id: 1, author_username: 'alice', from_moderator: false, body: 'Please help', created: '2026-11-01T10:00:00Z' },
    { id: 2, author_username: null, from_moderator: true, body: 'On it', created: '2026-11-01T11:00:00Z' },
  ],
};

function renderPage() {
  const store = configureStore({ reducer: { auth: authReducer } });
  store.dispatch(setUser({ id: 7, username: 'mod' } as never));
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/modmail/3']}>
        <Routes>
          <Route path="/modmail/:id" element={<ModmailThreadPage />} />
        </Routes>
      </MemoryRouter>
    </Provider>,
  );
}

const creatorThread = {
  id: 3, community: 'py', subject: 'Help', status: 'open' as const,
  creator_username: 'alice', unread: false, created: '', updated: '',
};

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.listModmailMessages).mockResolvedValue(messages as never);
  vi.mocked(api.markModmailRead).mockResolvedValue(undefined);
});

it('shows the mod team instead of a moderator name to the creator and hides moderator controls', async () => {
  vi.mocked(api.getModmailThread).mockResolvedValue(creatorThread);
  renderPage();
  expect(await screen.findByText('On it')).toBeInTheDocument();
  expect(screen.getByText(/Moderators/)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Archive' })).not.toBeInTheDocument();
  expect(screen.queryByLabelText('Internal note')).not.toBeInTheDocument();
  expect(api.markModmailRead).toHaveBeenCalledWith(3);
});

it('lets a moderator send an internal note and archive the thread', async () => {
  vi.mocked(api.getModmailThread).mockResolvedValue({ ...creatorThread, assigned_to: null, assigned_to_username: null });
  vi.mocked(api.sendModmailMessage).mockResolvedValue({
    id: 9, author_username: 'mod', from_moderator: true, body: 'psst', is_internal: true, created: '2026-11-01T12:00:00Z',
  });
  vi.mocked(api.updateModmailThread).mockResolvedValue({ ...creatorThread, status: 'archived', assigned_to: null });
  renderPage();
  await userEvent.type(await screen.findByLabelText('Write a reply'), 'psst');
  await userEvent.click(screen.getByLabelText('Internal note'));
  await userEvent.click(screen.getByRole('button', { name: 'Send' }));
  await waitFor(() => expect(api.sendModmailMessage).toHaveBeenCalledWith(3, 'psst', true));
  await userEvent.click(screen.getByRole('button', { name: 'Archive' }));
  await waitFor(() => expect(api.updateModmailThread).toHaveBeenCalledWith(3, { status: 'archived' }));
  await userEvent.click(screen.getByRole('button', { name: 'Assign to me' }));
  await waitFor(() => expect(api.updateModmailThread).toHaveBeenCalledWith(3, { assigned_to: 7 }));
});

it('shows not found for an inaccessible thread', async () => {
  vi.mocked(api.getModmailThread).mockRejectedValue(new Error('404'));
  renderPage();
  expect(await screen.findByText('Conversation not found.')).toBeInTheDocument();
});

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import '@/i18n';
import { ModmailListPage } from './ModmailListPage';
import * as api from '@/api/modmail';

vi.mock('@/api/modmail');
const page = (results: unknown[]) => ({ count: results.length, next: null, previous: null, results }) as never;
const thread = { id: 4, community: 'py', subject: 'Ban appeal', status: 'open', creator_username: 'alice', unread: true, created: '', updated: '2026-11-01T10:00:00Z' };

beforeEach(() => vi.resetAllMocks());

it('lists the moderators inbox and switches to archived', async () => {
  vi.mocked(api.listModmailInbox).mockResolvedValue(page([thread]));
  render(
    <MemoryRouter initialEntries={['/c/py/modmail']}>
      <Routes><Route path="/c/:slug/modmail" element={<ModmailListPage inbox />} /></Routes>
    </MemoryRouter>,
  );
  expect(await screen.findByText('Ban appeal')).toBeInTheDocument();
  expect(screen.getByRole('img', { name: 'Unread' })).toBeInTheDocument();
  await userEvent.click(screen.getByRole('tab', { name: 'Archived' }));
  await waitFor(() => expect(api.listModmailInbox).toHaveBeenCalledWith('py', 'archived', 1));
});

it('lists the users own threads', async () => {
  vi.mocked(api.listMyModmail).mockResolvedValue(page([]));
  render(<MemoryRouter initialEntries={['/modmail']}><Routes><Route path="/modmail" element={<ModmailListPage />} /></Routes></MemoryRouter>);
  expect(await screen.findByText('No conversations here.')).toBeInTheDocument();
});

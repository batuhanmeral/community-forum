import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { Community } from '@/features/communities/types';
import { ModPage } from './ModPage';
import * as communitiesApi from '@/api/communities';
import * as moderationApi from '@/api/moderation';
import * as postsApi from '@/api/posts';

vi.mock('@/api/communities', () => ({
  getCommunity: vi.fn(),
  updateCommunity: vi.fn(),
  listFlairs: vi.fn(),
  createFlair: vi.fn(),
  deleteFlair: vi.fn(),
  listRules: vi.fn(),
  createRule: vi.fn(),
  updateRule: vi.fn(),
  deleteRule: vi.fn(),
}));
vi.mock('@/api/moderation', () => ({
  listModReports: vi.fn(),
  resolveReport: vi.fn(),
  dismissReport: vi.fn(),
  banUser: vi.fn(),
  setMemberRole: vi.fn(),
  listModLog: vi.fn(),
  listBans: vi.fn(),
  unbanUser: vi.fn(),
}));
vi.mock('@/api/posts', () => ({
  listApprovalQueue: vi.fn(),
  approvePost: vi.fn(),
  rejectPost: vi.fn(),
}));

const empty = { count: 0, next: null, previous: null, results: [] };

const adminCommunity = {
  id: 1,
  slug: 'py',
  name: 'Py',
  description: '',
  avatar: null,
  is_nsfw: false,
  requires_approval: false,
  creator: 1,
  created_at: '2026-10-01T00:00:00Z',
  member_count: 3,
  is_member: true,
  is_banned: false,
  my_role: 'admin',
  my_notify_level: 'all',
  banned_keywords: '',
} as Community;

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/c/py/mod']}>
      <Routes>
        <Route path="/c/:slug/mod" element={<ModPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('ModPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(communitiesApi.getCommunity).mockResolvedValue(adminCommunity);
    vi.mocked(communitiesApi.listFlairs).mockResolvedValue([]);
    vi.mocked(communitiesApi.listRules).mockResolvedValue([]);
    vi.mocked(moderationApi.listModReports).mockResolvedValue(empty);
    vi.mocked(moderationApi.listModLog).mockResolvedValue(empty);
    vi.mocked(moderationApi.listBans).mockResolvedValue(empty);
    vi.mocked(postsApi.listApprovalQueue).mockResolvedValue(empty);
  });

  it('sends requires_approval when an admin turns approval on', async () => {
    vi.mocked(communitiesApi.updateCommunity).mockResolvedValue({
      ...adminCommunity,
      requires_approval: true,
    });
    renderPage();
    await userEvent.click(await screen.findByLabelText(/hold new posts/i));
    await userEvent.click(screen.getByRole('button', { name: 'Save settings' }));
    await waitFor(() =>
      expect(communitiesApi.updateCommunity).toHaveBeenCalledWith(
        'py',
        expect.objectContaining({ requires_approval: true }),
      ),
    );
  });

  it('shows the approval queue', async () => {
    renderPage();
    expect(await screen.findByText('Approval queue')).toBeInTheDocument();
  });

  it('shows the rules card', async () => {
    renderPage();
    expect(await screen.findByText('Rules')).toBeInTheDocument();
  });

  it('refreshes the banned list after a ban', async () => {
    vi.mocked(moderationApi.banUser).mockResolvedValue({} as never);
    renderPage();
    await screen.findByText('Banned members');
    // The ban and role cards both use placeholder "username", so pick the ban input by name.
    const input = document.querySelector<HTMLInputElement>('input[name="ban-username"]')!;
    await userEvent.type(input, 'spammer');
    await userEvent.click(screen.getByRole('button', { name: 'Ban user' }));
    await waitFor(() => expect(moderationApi.listBans).toHaveBeenCalledTimes(2));
  });
});

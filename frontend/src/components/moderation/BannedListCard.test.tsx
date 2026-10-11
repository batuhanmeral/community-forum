import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { BannedListCard } from './BannedListCard';
import * as moderationApi from '@/api/moderation';
import type { BannedMember } from '@/api/moderation';

vi.mock('@/api/moderation', () => ({ listBans: vi.fn(), unbanUser: vi.fn() }));

const api = vi.mocked(moderationApi);

const spammer: BannedMember = {
  id: 7,
  username: 'spammer',
  avatar: null,
  banned_by_username: 'adm',
  banned_at: '2026-10-01T00:00:00Z',
  joined_at: '2026-09-01T00:00:00Z',
};

function renderCard() {
  return render(
    <MemoryRouter>
      <BannedListCard slug="py" />
    </MemoryRouter>,
  );
}

describe('BannedListCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listBans.mockResolvedValue({ count: 1, next: null, previous: null, results: [spammer] });
  });

  it('shows who issued each ban', async () => {
    renderCard();
    expect(await screen.findByText('u/spammer')).toBeInTheDocument();
    expect(screen.getByText(/banned by u\/adm/)).toBeInTheDocument();
  });

  it('lifts a ban and drops the row', async () => {
    api.unbanUser.mockResolvedValue();
    renderCard();
    await userEvent.click(await screen.findByRole('button', { name: 'Unban' }));
    await waitFor(() => expect(screen.queryByText('u/spammer')).not.toBeInTheDocument());
    expect(api.unbanUser).toHaveBeenCalledWith('py', 'spammer');
  });

  it('keeps the row and shows the server reason when the ban is protected', async () => {
    api.unbanUser.mockRejectedValue({
      response: { data: { detail: 'Only a moderator ranked at least as high …' } },
    });
    renderCard();
    await userEvent.click(await screen.findByRole('button', { name: 'Unban' }));
    expect(await screen.findByText(/ranked at least as high/)).toBeInTheDocument();
    expect(screen.getByText('u/spammer')).toBeInTheDocument();
  });
});

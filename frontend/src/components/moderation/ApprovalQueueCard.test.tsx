import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import type { Post } from '@/features/posts/types';
import { ApprovalQueueCard } from './ApprovalQueueCard';
import * as postsApi from '@/api/posts';

vi.mock('@/api/posts', () => ({
  listApprovalQueue: vi.fn(),
  approvePost: vi.fn(),
  rejectPost: vi.fn(),
}));

const api = vi.mocked(postsApi);

function held(id: number): Post {
  return {
    id,
    title: `held ${id}`,
    author_username: 'bob',
    created_at: '2026-10-01T00:00:00Z',
  } as unknown as Post;
}

function page(results: Post[], next: string | null = null) {
  return { count: results.length, next, previous: null, results };
}

function renderCard() {
  return render(
    <MemoryRouter>
      <ApprovalQueueCard slug="py" />
    </MemoryRouter>,
  );
}

describe('ApprovalQueueCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listApprovalQueue.mockResolvedValue(page([held(1)]));
  });

  it('links each pending post', async () => {
    renderCard();
    expect(await screen.findByRole('link', { name: 'held 1' })).toHaveAttribute('href', '/posts/1');
    expect(api.listApprovalQueue).toHaveBeenCalledWith('py', 1);
  });

  it('removes a post once approved', async () => {
    api.approvePost.mockResolvedValue();
    renderCard();
    await userEvent.click(await screen.findByRole('button', { name: 'Approve' }));
    await waitFor(() => expect(screen.queryByText('held 1')).not.toBeInTheDocument());
    expect(api.approvePost).toHaveBeenCalledWith(1);
  });

  it('removes a post once rejected', async () => {
    api.rejectPost.mockResolvedValue();
    renderCard();
    await userEvent.click(await screen.findByRole('button', { name: 'Reject' }));
    await waitFor(() => expect(screen.queryByText('held 1')).not.toBeInTheDocument());
    expect(api.rejectPost).toHaveBeenCalledWith(1);
  });

  it('keeps the post and explains when the action fails', async () => {
    api.approvePost.mockRejectedValue(new Error('500'));
    renderCard();
    await userEvent.click(await screen.findByRole('button', { name: 'Approve' }));
    expect(await screen.findByText('Action failed. Try again.')).toBeInTheDocument();
    expect(screen.getByText('held 1')).toBeInTheDocument();
  });

  it('shows the empty state', async () => {
    api.listApprovalQueue.mockResolvedValue(page([]));
    renderCard();
    expect(await screen.findByText('No posts awaiting approval.')).toBeInTheDocument();
  });

  it('shows a load error instead of the empty state', async () => {
    api.listApprovalQueue.mockRejectedValue(new Error('down'));
    renderCard();
    expect(await screen.findByText(/Could not load this list/)).toBeInTheDocument();
    expect(screen.queryByText('No posts awaiting approval.')).not.toBeInTheDocument();
  });
});

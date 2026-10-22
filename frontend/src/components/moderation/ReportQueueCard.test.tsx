import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ReportQueueCard } from './ReportQueueCard';
import * as moderationApi from '@/api/moderation';
import type { Report } from '@/api/moderation';
import i18n from '@/i18n';
import { resetLanguage, visibleText } from '@/test/i18nHelpers';

vi.mock('@/api/moderation', () => ({
  listModReports: vi.fn(),
  resolveReport: vi.fn(),
  dismissReport: vi.fn(),
}));

const api = vi.mocked(moderationApi);

function report(id: number, overrides: Partial<Report> = {}): Report {
  return {
    id,
    target_type: 'comment',
    object_id: 5,
    target_preview: { text: `comment ${id}`, link: `/posts/1#comment-${id}`, is_deleted: false },
    reason: 'Spam',
    status: 'open',
    created_at: '2026-10-01T00:00:00Z',
    ...overrides,
  };
}

function page(results: Report[], next: string | null = null) {
  return { count: results.length, next, previous: null, results };
}

function renderCard() {
  return render(
    <MemoryRouter>
      <ReportQueueCard slug="py" />
    </MemoryRouter>,
  );
}

describe('ReportQueueCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listModReports.mockResolvedValue(page([report(1)]));
  });

  it('links the reported content and never shows a reporter', async () => {
    renderCard();
    expect(await screen.findByRole('link', { name: 'comment 1' })).toHaveAttribute(
      'href',
      '/posts/1#comment-1',
    );
    expect(screen.queryByText(/by u\//)).not.toBeInTheDocument();
  });

  it('says when the reported content is gone', async () => {
    api.listModReports.mockResolvedValue(page([report(1, { target_preview: null })]));
    renderCard();
    expect(await screen.findByText('Content no longer available')).toBeInTheDocument();
  });

  it('loads more reports', async () => {
    api.listModReports
      .mockResolvedValueOnce(page([report(1)], 'p2'))
      .mockResolvedValueOnce(page([report(2)]));
    renderCard();
    await userEvent.click(await screen.findByRole('button', { name: 'Load more' }));
    expect(await screen.findByText('comment 2')).toBeInTheDocument();
    expect(api.listModReports).toHaveBeenLastCalledWith('py', 'open', 2);
  });

  it('starts over at page 1 when the status changes', async () => {
    renderCard();
    await screen.findByText('comment 1');
    await userEvent.click(screen.getByRole('button', { name: 'Resolved' }));
    await waitFor(() => expect(api.listModReports).toHaveBeenLastCalledWith('py', 'resolved', 1));
  });

  it('drops a report once resolved', async () => {
    api.resolveReport.mockResolvedValue(report(1, { status: 'resolved' }));
    renderCard();
    await userEvent.click(await screen.findByRole('button', { name: 'Resolve' }));
    await waitFor(() => expect(screen.queryByText('comment 1')).not.toBeInTheDocument());
    expect(api.resolveReport).toHaveBeenCalledWith('py', 1);
  });

  it('shows a load error instead of the empty state', async () => {
    api.listModReports.mockRejectedValue(new Error('down'));
    renderCard();
    expect(await screen.findByText(/Could not load this list/)).toBeInTheDocument();
    expect(screen.queryByText('No reports with this status.')).not.toBeInTheDocument();
  });

  it('keeps the deleted marker outside the truncated link', async () => {
    api.listModReports.mockResolvedValue(
      page([
        report(1, {
          target_preview: { text: 'x'.repeat(300), link: '/posts/1', is_deleted: true },
        }),
      ]),
    );
    renderCard();
    const link = await screen.findByRole('link');
    const marker = screen.getByText('(deleted)');
    expect(link.contains(marker)).toBe(false);
    expect(marker.closest('.truncate')).toBeNull();
  });

  it('switching report tabs clears the previous error', async () => {
    api.resolveReport.mockRejectedValue(new Error('500'));
    renderCard();
    await userEvent.click(await screen.findByRole('button', { name: 'Resolve' }));
    expect(await screen.findByText('Action failed. Try again.')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Resolved' }));
    expect(screen.queryByText('Action failed. Try again.')).not.toBeInTheDocument();
  });
});

describe('ReportQueueCard in Turkish', () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(resetLanguage);

  it('shows a removed comment preview in Turkish', async () => {
    api.listModReports.mockResolvedValue(
      page([report(1, { target_preview: { text: '[removed]', link: '/posts/1#comment-1', is_deleted: true } })]),
    );
    await i18n.changeLanguage('tr');
    renderCard();
    expect(await screen.findByRole('link', { name: '[kaldırıldı]' })).toBeInTheDocument();
    expect(visibleText()).not.toMatch(/\[(deleted|removed)\]/);
  });
});

import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { EditHistoryModal } from './EditHistoryModal';

const revision = {
  id: 1,
  title: 'Old title',
  body: '<b>old</b> body',
  edited_at: '2026-10-01T00:00:00Z',
  edited_by: 9,
  edited_by_username: 'bob',
};

describe('EditHistoryModal', () => {
  it('lists earlier versions as plain text', async () => {
    const load = vi.fn().mockResolvedValue({ count: 1, next: null, previous: null, results: [revision] });
    render(<EditHistoryModal open onClose={() => {}} load={load} />);
    expect(await screen.findByText('Old title')).toBeInTheDocument();
    // Revision bodies are markdown source; they must never be injected as HTML.
    expect(screen.getByText('<b>old</b> body')).toBeInTheDocument();
    expect(screen.getByText('Edited by u/bob', { exact: false })).toBeInTheDocument();
    expect(load).toHaveBeenCalledWith(1);
  });

  it('explains a failed load', async () => {
    const load = vi.fn().mockRejectedValue(new Error('403'));
    render(<EditHistoryModal open onClose={() => {}} load={load} />);
    expect(await screen.findByText('Could not load the edit history.')).toBeInTheDocument();
  });

  it('does not load while closed', () => {
    const load = vi.fn();
    render(<EditHistoryModal open={false} onClose={() => {}} load={load} />);
    expect(load).not.toHaveBeenCalled();
  });

  it('reports a failed load-more', async () => {
    const load = vi
      .fn()
      .mockResolvedValueOnce({ count: 2, next: 'p2', previous: null, results: [revision] })
      .mockRejectedValueOnce(new Error('down'));
    render(<EditHistoryModal open onClose={() => {}} load={load} />);
    await userEvent.click(await screen.findByRole('button', { name: 'Load more' }));
    expect(await screen.findByText('Could not load more versions.')).toBeInTheDocument();
    expect(screen.getByText('Old title')).toBeInTheDocument();
  });
});

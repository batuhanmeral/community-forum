import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { CommunityRule } from '@/features/communities/types';
import { RulesCard } from './RulesCard';
import * as communitiesApi from '@/api/communities';

vi.mock('@/api/communities', () => ({
  listRules: vi.fn(),
  createRule: vi.fn(),
  updateRule: vi.fn(),
  deleteRule: vi.fn(),
}));

const api = vi.mocked(communitiesApi);

function rule(id: number, short: string, order: number): CommunityRule {
  return { id, short, order, description: '', created_at: '2026-10-01T00:00:00Z' };
}

describe('RulesCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listRules.mockResolvedValue([rule(1, 'Be kind', 0)]);
  });

  it('adds a rule in order', async () => {
    api.createRule.mockResolvedValue(rule(2, 'No spam', 1));
    render(<RulesCard slug="py" />);
    await screen.findByText('Be kind');
    await userEvent.type(screen.getByLabelText('Rule'), 'No spam');
    await userEvent.clear(screen.getByLabelText('Order'));
    await userEvent.type(screen.getByLabelText('Order'), '1');
    await userEvent.click(screen.getByRole('button', { name: 'Add rule' }));
    await screen.findByText('No spam');
    expect(api.createRule).toHaveBeenCalledWith('py', { short: 'No spam', description: '', order: 1 });
    const items = screen.getAllByRole('listitem').map((li) => li.textContent);
    expect(items[0]).toContain('Be kind');
    expect(items[1]).toContain('No spam');
  });

  it('edits a rule', async () => {
    api.updateRule.mockResolvedValue(rule(1, 'Be very kind', 0));
    render(<RulesCard slug="py" />);
    const row = (await screen.findByText('Be kind')).closest('li')!;
    await userEvent.click(within(row).getByRole('button', { name: 'Edit' }));
    const field = screen.getByLabelText('Rule');
    await userEvent.clear(field);
    await userEvent.type(field, 'Be very kind');
    await userEvent.click(screen.getByRole('button', { name: 'Save rule' }));
    expect(await screen.findByText('Be very kind')).toBeInTheDocument();
    expect(api.updateRule).toHaveBeenCalledWith('py', 1, {
      short: 'Be very kind',
      description: '',
      order: 0,
    });
  });

  it('deletes a rule', async () => {
    api.deleteRule.mockResolvedValue();
    render(<RulesCard slug="py" />);
    const row = (await screen.findByText('Be kind')).closest('li')!;
    await userEvent.click(within(row).getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(screen.queryByText('Be kind')).not.toBeInTheDocument());
    expect(api.deleteRule).toHaveBeenCalledWith('py', 1);
    expect(await screen.findByText('No rules yet.')).toBeInTheDocument();
  });

  it('keeps the form and explains when saving fails', async () => {
    api.createRule.mockRejectedValue(new Error('400'));
    render(<RulesCard slug="py" />);
    await screen.findByText('Be kind');
    await userEvent.type(screen.getByLabelText('Rule'), 'Oops');
    await userEvent.click(screen.getByRole('button', { name: 'Add rule' }));
    expect(await screen.findByText('Could not save the rule.')).toBeInTheDocument();
    expect(screen.getByLabelText('Rule')).toHaveValue('Oops');
  });
});

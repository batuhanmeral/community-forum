import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it, vi } from 'vitest';
import '@/i18n';
import { RemovalReasonModal } from './RemovalReasonModal';

const mocks = vi.hoisted(() => ({ list: vi.fn() }));
vi.mock('@/api/moderation', () => ({ listRemovalReasons: mocks.list }));

beforeEach(() => {
  vi.clearAllMocks();
  mocks.list.mockResolvedValue([{ id: 4, title: 'Spam', body: 'No spam', order: 0 }]);
});

it('confirms with the chosen reason and note', async () => {
  const onConfirm = vi.fn().mockResolvedValue(undefined);
  render(<RemovalReasonModal open slug="py" required={false} onClose={vi.fn()} onConfirm={onConfirm} />);
  await screen.findByRole('option', { name: 'Spam' });
  await userEvent.selectOptions(screen.getByLabelText('Reason'), '4');
  await userEvent.type(screen.getByLabelText('Note to the author (optional)'), 'Third time');
  await userEvent.click(screen.getByRole('button', { name: 'Remove' }));
  await waitFor(() => expect(onConfirm).toHaveBeenCalledWith({ reason: 4, note: 'Third time' }));
});

it('removes without a reason when the community does not require one', async () => {
  const onConfirm = vi.fn().mockResolvedValue(undefined);
  render(<RemovalReasonModal open slug="py" required={false} onClose={vi.fn()} onConfirm={onConfirm} />);
  await screen.findByRole('option', { name: 'Spam' });
  await userEvent.click(screen.getByRole('button', { name: 'Remove' }));
  await waitFor(() => expect(onConfirm).toHaveBeenCalledWith({ reason: null, note: '' }));
});

it('blocks removal until a reason is chosen when one is required', async () => {
  const onConfirm = vi.fn().mockResolvedValue(undefined);
  render(<RemovalReasonModal open slug="py" required onClose={vi.fn()} onConfirm={onConfirm} />);
  await screen.findByRole('option', { name: 'Spam' });
  expect(screen.getByRole('button', { name: 'Remove' })).toBeDisabled();
  await userEvent.selectOptions(screen.getByLabelText('Reason'), '4');
  expect(screen.getByRole('button', { name: 'Remove' })).toBeEnabled();
});

it('shows an error when the removal fails', async () => {
  const onConfirm = vi.fn().mockRejectedValue(new Error('x'));
  render(<RemovalReasonModal open slug="py" required={false} onClose={vi.fn()} onConfirm={onConfirm} />);
  await screen.findByRole('option', { name: 'Spam' });
  await userEvent.click(screen.getByRole('button', { name: 'Remove' }));
  expect(await screen.findByRole('alert')).toBeInTheDocument();
});

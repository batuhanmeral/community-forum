import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it, vi } from 'vitest';
import '@/i18n';
import { RemovalReasonsCard } from './RemovalReasonsCard';

const mocks = vi.hoisted(() => ({ list: vi.fn(), create: vi.fn(), remove: vi.fn() }));
vi.mock('@/api/moderation', () => ({
  listRemovalReasons: mocks.list,
  createRemovalReason: mocks.create,
  deleteRemovalReason: mocks.remove,
}));

beforeEach(() => {
  vi.clearAllMocks();
  mocks.list.mockResolvedValue([{ id: 1, title: 'Spam', body: 'No spam', order: 0 }]);
});

it('lists, adds and deletes removal reasons', async () => {
  mocks.create.mockResolvedValue({ id: 2, title: 'Off topic', body: 'Stay on topic', order: 0 });
  render(<RemovalReasonsCard slug="py" />);
  expect(await screen.findByText('Spam')).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText('Title'), 'Off topic');
  await userEvent.type(screen.getByLabelText('Message to the author'), 'Stay on topic');
  await userEvent.click(screen.getByRole('button', { name: 'Add reason' }));
  await waitFor(() => expect(mocks.create).toHaveBeenCalledWith('py', 'Off topic', 'Stay on topic'));
  expect(await screen.findByText('Off topic')).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Delete reason: Spam' }));
  await waitFor(() => expect(mocks.remove).toHaveBeenCalledWith('py', 1));
});

it('lets an admin toggle the require-reason setting', async () => {
  const onChange = vi.fn().mockResolvedValue(undefined);
  render(<RemovalReasonsCard slug="py" required={false} onRequiredChange={onChange} />);
  await userEvent.click(await screen.findByRole('checkbox', { name: 'Require a reason when removing content' }));
  expect(onChange).toHaveBeenCalledWith(true);
});

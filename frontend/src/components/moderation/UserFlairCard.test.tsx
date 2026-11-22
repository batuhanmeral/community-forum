import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it, vi } from 'vitest';
import '@/i18n';
import { UserFlairCard } from './UserFlairCard';

const mocks = vi.hoisted(() => ({ list: vi.fn(), assign: vi.fn(), create: vi.fn(), remove: vi.fn() }));
vi.mock('@/api/communities', () => ({
  listUserFlairs: mocks.list, assignUserFlair: mocks.assign,
  createUserFlair: mocks.create, deleteUserFlair: mocks.remove,
}));
beforeEach(() => {
  vi.clearAllMocks();
  mocks.list.mockResolvedValue([{ id: 1, text: 'Helper', color: '#123456', order: 0 }]);
  mocks.assign.mockResolvedValue({});
});
it('selects and clears a membership flair', async () => {
  render(<UserFlairCard slug="py" canSelect isModerator={false} />);
  await screen.findByRole('option', { name: 'Helper' });
  await userEvent.selectOptions(screen.getByRole('combobox'), '1');
  await waitFor(() => expect(mocks.assign).toHaveBeenCalledWith('py', 1));
  await userEvent.selectOptions(screen.getByRole('combobox'), '');
  await waitFor(() => expect(mocks.assign).toHaveBeenLastCalledWith('py', null));
});
it('lets moderators define flair and delete a template', async () => {
  mocks.create.mockResolvedValue({ id: 2, text: 'Expert', color: '#888888', order: 0 });
  render(<UserFlairCard slug="py" canSelect isModerator />);
  await screen.findByRole('option', { name: 'Helper' });
  await userEvent.type(screen.getByLabelText('Flair text'), 'Expert');
  await userEvent.click(screen.getByRole('button', { name: 'Add flair' }));
  await waitFor(() => expect(mocks.create).toHaveBeenCalledWith('py', 'Expert', '#888888'));
  await userEvent.click(screen.getByRole('button', { name: 'Delete Helper' }));
  await waitFor(() => expect(mocks.remove).toHaveBeenCalledWith('py', 1));
});
it('shows a failed selection without losing the chosen value', async () => {
  mocks.assign.mockRejectedValue(new Error('offline'));
  render(<UserFlairCard slug="py" canSelect isModerator={false} />);
  await screen.findByRole('option', { name: 'Helper' });
  await userEvent.selectOptions(screen.getByRole('combobox'), '1');
  expect(await screen.findByRole('alert')).toBeInTheDocument();
  expect(screen.getByRole('combobox')).toHaveValue('');
});

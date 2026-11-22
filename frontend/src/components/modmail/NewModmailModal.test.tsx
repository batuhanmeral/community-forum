import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import '@/i18n';
import { NewModmailModal } from './NewModmailModal';
import * as api from '@/api/modmail';

vi.mock('@/api/modmail');
const navigate = vi.hoisted(() => vi.fn());
vi.mock('react-router-dom', async (orig) => ({ ...(await orig<typeof import('react-router-dom')>()), useNavigate: () => navigate }));

beforeEach(() => vi.resetAllMocks());

function renderModal(onClose = vi.fn()) {
  render(
    <MemoryRouter>
      <NewModmailModal open slug="py" onClose={onClose} />
    </MemoryRouter>,
  );
  return onClose;
}

it('opens a thread and navigates to it', async () => {
  vi.mocked(api.createModmailThread).mockResolvedValue({ id: 12 } as never);
  const onClose = renderModal();
  expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled();
  await userEvent.type(screen.getByLabelText('Subject'), 'Appeal');
  await userEvent.type(screen.getByLabelText('Message'), 'Please unban me');
  await userEvent.click(screen.getByRole('button', { name: 'Send' }));
  await waitFor(() => expect(api.createModmailThread).toHaveBeenCalledWith('py', 'Appeal', 'Please unban me'));
  expect(navigate).toHaveBeenCalledWith('/modmail/12');
  expect(onClose).toHaveBeenCalled();
});

it('explains the daily limit', async () => {
  vi.mocked(api.createModmailThread).mockRejectedValue({ response: { status: 429 } });
  renderModal();
  await userEvent.type(screen.getByLabelText('Subject'), 'Again');
  await userEvent.type(screen.getByLabelText('Message'), 'x');
  await userEvent.click(screen.getByRole('button', { name: 'Send' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('daily limit');
});

import { beforeEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@/i18n';
import { PushCard } from './PushCard';
import * as push from '@/lib/push';
import * as api from '@/api/push';

vi.mock('@/lib/push');
vi.mock('@/api/push');

const prefs = {
  enabled: true,
  types: { messages: true, replies: true, mentions: true, follows: true, moderation: true },
};

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.getPushPreferences).mockResolvedValue(prefs);
});

it('explains when the browser cannot do push', async () => {
  vi.mocked(push.getPushState).mockResolvedValue('unsupported');
  render(<PushCard />);
  expect(await screen.findByText(/doesn't support push/)).toBeInTheDocument();
});

it('explains when the server has push off', async () => {
  vi.mocked(push.getPushState).mockResolvedValue('unavailable');
  render(<PushCard />);
  expect(await screen.findByText(/not available on this server/)).toBeInTheDocument();
});

it('tells the user to unblock notifications and disables the button', async () => {
  vi.mocked(push.getPushState).mockResolvedValue('denied');
  render(<PushCard />);
  expect(await screen.findByText(/blocked for this site/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Turn on push notifications' })).toBeDisabled();
});

it('turns push on, then shows the per-type switches', async () => {
  vi.mocked(push.getPushState).mockResolvedValue('off');
  vi.mocked(push.enablePush).mockResolvedValue('on');
  render(<PushCard />);
  await userEvent.click(await screen.findByRole('button', { name: 'Turn on push notifications' }));
  await waitFor(() => expect(push.enablePush).toHaveBeenCalled());
  expect(await screen.findByRole('checkbox', { name: 'Messages' })).toBeChecked();
});

it('saves a changed type and can turn push off', async () => {
  vi.mocked(push.getPushState).mockResolvedValue('on');
  vi.mocked(api.updatePushPreferences).mockResolvedValue({
    ...prefs,
    types: { ...prefs.types, follows: false },
  });
  render(<PushCard />);
  await userEvent.click(await screen.findByRole('checkbox', { name: 'New followers' }));
  await waitFor(() => expect(api.updatePushPreferences).toHaveBeenCalledWith({ types: { follows: false } }));
  expect(screen.getByRole('checkbox', { name: 'New followers' })).not.toBeChecked();
  await userEvent.click(screen.getByRole('button', { name: 'Turn off on this device' }));
  await waitFor(() => expect(push.disablePush).toHaveBeenCalled());
  expect(await screen.findByRole('button', { name: 'Turn on push notifications' })).toBeInTheDocument();
});

it('shows an error when enabling fails', async () => {
  vi.mocked(push.getPushState).mockResolvedValue('off');
  vi.mocked(push.enablePush).mockRejectedValue(new Error('x'));
  render(<PushCard />);
  await userEvent.click(await screen.findByRole('button', { name: 'Turn on push notifications' }));
  expect(await screen.findByRole('alert')).toBeInTheDocument();
});

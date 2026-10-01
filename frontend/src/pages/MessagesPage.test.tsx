import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer, { setUser } from '@/features/auth/authSlice';
import messagingReducer from '@/features/messaging/messagingSlice';
import type { Conversation, Message } from '@/features/messaging/types';
import { MessagesPage } from './MessagesPage';
import * as messagingApi from '@/api/messaging';

vi.mock('@/api/messaging', () => ({
  listConversations: vi.fn(),
  listMessages: vi.fn(),
  markConversationRead: vi.fn(),
  sendMessage: vi.fn(),
  startConversation: vi.fn(),
}));

const api = vi.mocked(messagingApi);

const conversation: Conversation = {
  id: 1,
  participant_a: 1,
  participant_b: 2,
  other: { id: 2, username: 'bob' },
  last_message: null,
  unread_count: 0,
  created_at: '2026-10-01T00:00:00Z',
};

const otherConversation: Conversation = {
  ...conversation,
  id: 2,
  participant_b: 3,
  other: { id: 3, username: 'carol' },
};

function msg(id: number, sender = 2, conversationId = 1): Message {
  return {
    id,
    conversation: conversationId,
    sender,
    sender_username: sender === 1 ? 'alice' : 'bob',
    body: `m${id}`,
    created_at: `2026-10-01T00:0${id}:00Z`,
    read_at: null,
  };
}

function page(results: Message[], next: string | null) {
  return { count: results.length, next, previous: null, results };
}

function renderAt(path: string) {
  const store = configureStore({ reducer: { auth: authReducer, messaging: messagingReducer } });
  store.dispatch(
    setUser({
      id: 1,
      username: 'alice',
      email: 'a@x.com',
      email_verified: true,
      avatar: null,
      bio: '',
      show_nsfw: false,
      post_karma: 0,
      comment_karma: 0,
    }),
  );
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/messages" element={<MessagesPage />} />
          <Route path="/messages/:id" element={<MessagesPage />} />
        </Routes>
      </MemoryRouter>
    </Provider>,
  );
}

function isBefore(a: HTMLElement, b: HTMLElement) {
  return Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
}

beforeAll(() => {
  Element.prototype.scrollTo = vi.fn() as unknown as Element['scrollTo'];
});

describe('MessagesPage chat', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listConversations.mockResolvedValue([conversation]);
    api.markConversationRead.mockResolvedValue();
  });

  it('shows the newest page oldest-to-newest and loads older messages on demand', async () => {
    api.listMessages
      .mockResolvedValueOnce(page([msg(3), msg(2)], 'p2'))
      .mockResolvedValueOnce(page([msg(2), msg(1)], null));
    renderAt('/messages/1');

    const m2 = await screen.findByText('m2');
    expect(isBefore(m2, screen.getByText('m3'))).toBe(true);

    await userEvent.click(screen.getByRole('button', { name: 'Load older messages' }));
    const m1 = await screen.findByText('m1');
    expect(isBefore(m1, screen.getByText('m2'))).toBe(true);
    expect(screen.getAllByText('m2')).toHaveLength(1);
    expect(api.listMessages).toHaveBeenLastCalledWith(1, 2);
  });

  it('shows the API error when sending fails', async () => {
    api.listMessages.mockResolvedValue(page([], null));
    api.sendMessage.mockRejectedValue({
      response: { data: { detail: 'You cannot message this user.' } },
    });
    renderAt('/messages/1');

    await userEvent.type(await screen.findByPlaceholderText(/message u\/bob/i), 'hello');
    await userEvent.click(screen.getByRole('button', { name: 'Send' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('You cannot message this user.');
  });
});

describe('MessagesPage chat edge cases', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listConversations.mockResolvedValue([conversation, otherConversation]);
    api.markConversationRead.mockResolvedValue();
  });

  it('ignores a stale older-page response after switching conversation', async () => {
    let resolveOlder!: (value: ReturnType<typeof page>) => void;
    api.listMessages.mockImplementation((conversationId, pageNumber) => {
      if (conversationId === 1 && pageNumber === 2) {
        return new Promise<ReturnType<typeof page>>((resolve) => {
          resolveOlder = resolve;
        });
      }
      if (conversationId === 1) return Promise.resolve(page([msg(3)], 'p2'));
      return Promise.resolve(page([msg(9, 2, 2)], null));
    });
    renderAt('/messages/1');

    await userEvent.click(await screen.findByRole('button', { name: 'Load older messages' }));
    await userEvent.click(screen.getByRole('link', { name: /carol/ }));
    await screen.findByText('m9');

    await act(async () => resolveOlder(page([msg(1)], null)));
    expect(screen.queryByText('m1')).not.toBeInTheDocument();
    expect(screen.getByText('m9')).toBeInTheDocument();
  });

  it('shows an inline error and keeps the button when loading older messages fails', async () => {
    api.listMessages
      .mockResolvedValueOnce(page([msg(3)], 'p2'))
      .mockRejectedValueOnce(new Error('network'));
    renderAt('/messages/1');

    await userEvent.click(await screen.findByRole('button', { name: 'Load older messages' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load older messages.');
    expect(screen.getByRole('button', { name: 'Load older messages' })).toBeInTheDocument();
  });
});

describe('MessagesPage polling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listConversations.mockResolvedValue([conversation]);
    api.markConversationRead.mockResolvedValue();
  });

  afterEach(() => vi.useRealTimers());

  it('merges new messages from a poll without duplicates', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    api.listMessages
      .mockResolvedValueOnce(page([msg(1)], null))
      .mockResolvedValue(page([msg(3), msg(2, 1), msg(1)], null));
    api.sendMessage.mockResolvedValue(msg(2, 1));
    renderAt('/messages/1');

    await user.type(await screen.findByPlaceholderText(/message u\/bob/i), 'm2');
    await user.click(screen.getByRole('button', { name: 'Send' }));
    await screen.findByText('m2');

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(await screen.findByText('m3')).toBeInTheDocument();
    expect(screen.getAllByText('m2')).toHaveLength(1);
    expect(api.markConversationRead).toHaveBeenCalledTimes(2);
  });

  it('keeps messages ordered by time when a poll brings an earlier message', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    api.listMessages
      .mockResolvedValueOnce(page([msg(1)], null))
      .mockResolvedValue(page([msg(5, 1), msg(3), msg(1)], null));
    api.sendMessage.mockResolvedValue(msg(5, 1));
    renderAt('/messages/1');

    await user.type(await screen.findByPlaceholderText(/message u\/bob/i), 'm5');
    await user.click(screen.getByRole('button', { name: 'Send' }));
    await screen.findByText('m5');

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    const m3 = await screen.findByText('m3');
    expect(isBefore(m3, screen.getByText('m5'))).toBe(true);
  });

  it('replaces the list when a poll page does not overlap what is loaded', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    api.listMessages
      .mockResolvedValueOnce(page([msg(1)], null))
      .mockResolvedValue(page([msg(4), msg(3)], 'p2'));
    renderAt('/messages/1');
    await screen.findByText('m1');

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(await screen.findByText('m4')).toBeInTheDocument();
    expect(screen.queryByText('m1')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Load older messages' })).toBeInTheDocument();
  });

  it('does not duplicate a sent message when a poll resolves in the same tick', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    let resolveSend!: (value: Message) => void;
    let resolvePoll!: (value: ReturnType<typeof page>) => void;
    api.listMessages
      .mockResolvedValueOnce(page([msg(1)], null))
      .mockImplementationOnce(
        () =>
          new Promise<ReturnType<typeof page>>((resolve) => {
            resolvePoll = resolve;
          }),
      );
    api.sendMessage.mockImplementation(
      () =>
        new Promise<Message>((resolve) => {
          resolveSend = resolve;
        }),
    );
    renderAt('/messages/1');

    await user.type(await screen.findByPlaceholderText(/message u\/bob/i), 'm2');
    await user.click(screen.getByRole('button', { name: 'Send' }));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });

    // Both responses settle before React flushes the send's state update.
    await act(async () => {
      resolveSend(msg(2, 1));
      resolvePoll(page([msg(2, 1), msg(1)], null));
    });
    expect(screen.getAllByText('m2')).toHaveLength(1);
  });
});

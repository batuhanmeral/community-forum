import { describe, it, expect, vi, afterEach } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CommentForm } from './CommentForm';
import i18n from '@/i18n';
import { resetLanguage, visibleText } from '@/test/i18nHelpers';

vi.mock('@/api/search', () => ({ searchUsers: vi.fn() }));

describe('CommentForm', () => {
  it('shows the API detail and keeps the text when submit rejects', async () => {
    const onSubmit = vi.fn().mockRejectedValue({
      response: { data: { detail: 'You are banned from this community.' } },
    });
    render(<CommentForm onSubmit={onSubmit} />);
    await userEvent.type(screen.getByRole('textbox'), 'hello');
    await userEvent.click(screen.getByRole('button', { name: 'Comment' }));
    expect(await screen.findByText('You are banned from this community.')).toBeInTheDocument();
    expect(screen.getByRole('textbox')).toHaveValue('hello');
  });

  it('falls back to a generic message without an API detail', async () => {
    render(<CommentForm onSubmit={vi.fn().mockRejectedValue(new Error('x'))} />);
    await userEvent.type(screen.getByRole('textbox'), 'hello');
    await userEvent.click(screen.getByRole('button', { name: 'Comment' }));
    expect(await screen.findByText('Could not post your comment.')).toBeInTheDocument();
  });

  describe('with fake timers', () => {
    afterEach(() => vi.useRealTimers());

    it('leaves no pending timer after unmounting a blurred form', () => {
      vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
      const { unmount } = render(<CommentForm onSubmit={vi.fn()} />);
      const textarea = screen.getByRole('textbox');
      act(() => textarea.focus());
      act(() => textarea.blur());
      // jsdom schedules 0ms selection timers on focus/blur; only the 150ms blur timer is ours.
      vi.advanceTimersByTime(0);
      unmount();
      expect(vi.getTimerCount()).toBe(0);
    });
  });
});

describe('CommentForm in Turkish', () => {
  const ENGLISH_PROBE = /\b(Write a comment|Comment|Cancel)\b/;

  afterEach(resetLanguage);

  it('renders no English in Turkish', async () => {
    await i18n.changeLanguage('tr');
    render(<CommentForm onSubmit={vi.fn()} onCancel={vi.fn()} />);
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
  });
});
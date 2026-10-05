import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CommentForm } from './CommentForm';

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
});

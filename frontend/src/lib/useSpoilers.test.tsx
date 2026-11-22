import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useSpoilers } from './useSpoilers';

function Body({ html }: { html: string }) {
  const [ref, onClick, onKeyDown] = useSpoilers(html);
  return (
    <div
      data-testid="body"
      ref={ref}
      onClick={onClick}
      onKeyDown={onKeyDown}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

const HTML = '<p>a <span class="spoiler">twist</span> b</p>';

describe('useSpoilers', () => {
  it('turns spoiler spans into labelled, focusable buttons', () => {
    render(<Body html={HTML} />);
    const el = screen.getByRole('button', { name: 'Hidden spoiler text, press to reveal' });
    expect(el).toHaveAttribute('tabindex', '0');
    expect(el).toHaveAttribute('aria-expanded', 'false');
    expect(el).not.toHaveClass('spoiler-revealed');
  });

  it('reveals on click and drops the button semantics', async () => {
    render(<Body html={HTML} />);
    await userEvent.click(screen.getByRole('button'));
    const el = screen.getByText('twist');
    expect(el).toHaveClass('spoiler-revealed');
    expect(el).toHaveAttribute('aria-expanded', 'true');
    expect(screen.queryByRole('button')).toBeNull();
  });

  it.each(['{Enter}', ' '])('reveals from the keyboard with %j', async (key) => {
    const user = userEvent.setup();
    render(<Body html={HTML} />);
    await user.tab();
    expect(screen.getByRole('button')).toHaveFocus();
    await user.keyboard(key);
    expect(screen.getByText('twist')).toHaveClass('spoiler-revealed');
  });

  it('reveals only the clicked spoiler', async () => {
    render(<Body html={'<span class="spoiler">one</span><span class="spoiler">two</span>'} />);
    await userEvent.click(screen.getAllByRole('button')[0]);
    expect(screen.getByText('one')).toHaveClass('spoiler-revealed');
    expect(screen.getByText('two')).not.toHaveClass('spoiler-revealed');
  });
});

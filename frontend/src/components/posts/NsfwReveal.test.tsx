import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { NsfwReveal } from './NsfwReveal';

describe('NsfwReveal', () => {
  it('hides the media until the reveal button is pressed', async () => {
    const user = userEvent.setup();
    render(
      <NsfwReveal>
        <img alt="pic" src="/x.jpg" />
      </NsfwReveal>,
    );
    expect(screen.getByAltText('pic').closest('[aria-hidden="true"]')).not.toBeNull();
    await user.click(screen.getByRole('button', { name: 'Show NSFW content' }));
    expect(screen.queryByRole('button', { name: 'Show NSFW content' })).toBeNull();
    expect(screen.getByAltText('pic').closest('[aria-hidden="true"]')).toBeNull();
  });

  // The reveal button disappears on press; without a new target focus would fall back to <body>.
  it('moves focus to the revealed media when revealed from the keyboard', async () => {
    const user = userEvent.setup();
    render(
      <NsfwReveal>
        <img alt="pic" src="/x.jpg" />
      </NsfwReveal>,
    );
    await user.tab();
    expect(screen.getByRole('button', { name: 'Show NSFW content' })).toHaveFocus();
    await user.keyboard('{Enter}');
    const wrapper = screen.getByAltText('pic').closest('[tabindex="-1"]');
    expect(wrapper).not.toBeNull();
    expect(wrapper).toHaveFocus();
  });
});


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
});

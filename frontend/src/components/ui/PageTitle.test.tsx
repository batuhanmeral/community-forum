import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { PageTitle } from './PageTitle';

describe('PageTitle', () => {
  it('sets the document title', () => {
    const { rerender } = render(<PageTitle title="Saved" />);
    expect(document.title).toBe('Saved · Nexus');
    rerender(<PageTitle />);
    expect(document.title).toBe('Nexus');
  });
});

import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/react';
import { FeedLink } from './FeedLink';

describe('FeedLink', () => {
  it('puts an Atom alternate link into the document head', () => {
    render(<FeedLink path="/communities/py/feed.atom" title="c/py" />);
    const link = document.head.querySelector('link[rel="alternate"][type="application/atom+xml"]');
    expect(link).not.toBeNull();
    expect(link?.getAttribute('href')).toMatch(/\/communities\/py\/feed\.atom$/);
    expect(link?.getAttribute('title')).toBe('c/py');
  });
});

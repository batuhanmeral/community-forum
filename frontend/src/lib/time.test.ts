import { describe, it, expect, vi, afterEach } from 'vitest';
import i18n from '@/i18n';
import { timeAgo } from './time';

const NOW = new Date('2026-06-24T12:00:00Z').getTime();

afterEach(async () => {
  vi.useRealTimers();
  await i18n.changeLanguage('en');
});

function at(offsetSeconds: number): string {
  return new Date(NOW + offsetSeconds * 1000).toISOString();
}

describe('timeAgo', () => {
  // Exact wording depends on ICU, so match the magnitude, unit and direction.
  it.each([
    [-3 * 60 * 60, /3\s*h.*ago/],
    [-2 * 60 * 60 * 24, /2\s*d.*ago/],
    // Polls "close" in the future — the formatter should produce an "in …" phrasing.
    [5 * 60 * 60, /in 5\s*h/],
    [-10, /10\s*s/],
  ] as const)('formats an offset of %is', (offset, expected) => {
    vi.spyOn(Date, 'now').mockReturnValue(NOW);
    expect(timeAgo(at(offset))).toMatch(expected);
  });

  it('timeAgo follows the UI language', async () => {
    vi.spyOn(Date, 'now').mockReturnValue(NOW);
    await i18n.changeLanguage('tr');
    const expected = new Intl.RelativeTimeFormat('tr', { numeric: 'auto', style: 'narrow' }).format(-2, 'hour');
    expect(timeAgo(at(-2 * 60 * 60))).toBe(expected);
  });
});

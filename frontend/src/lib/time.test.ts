import { describe, it, expect, vi, afterEach } from 'vitest';
import { timeAgo } from './time';

const NOW = new Date('2026-06-24T12:00:00Z').getTime();

afterEach(() => {
  vi.useRealTimers();
});

function at(offsetSeconds: number): string {
  return new Date(NOW + offsetSeconds * 1000).toISOString();
}

describe('timeAgo', () => {
  it('formats a time a few hours in the past', () => {
    vi.spyOn(Date, 'now').mockReturnValue(NOW);
    // Exact wording depends on ICU; assert the magnitude/unit/"ago" shape.
    expect(timeAgo(at(-3 * 60 * 60))).toMatch(/3\s*h.*ago/);
  });

  it('formats a time several days in the past', () => {
    vi.spyOn(Date, 'now').mockReturnValue(NOW);
    expect(timeAgo(at(-2 * 60 * 60 * 24))).toMatch(/2\s*d.*ago/);
  });

  it('formats a future time', () => {
    vi.spyOn(Date, 'now').mockReturnValue(NOW);
    // Polls "close" in the future — the formatter should produce an "in …" phrasing.
    expect(timeAgo(at(5 * 60 * 60))).toMatch(/in 5\s*h/);
  });

  it('uses seconds for very recent timestamps', () => {
    vi.spyOn(Date, 'now').mockReturnValue(NOW);
    expect(timeAgo(at(-10))).toMatch(/10\s*s/);
  });
});

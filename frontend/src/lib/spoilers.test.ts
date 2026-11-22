import { describe, expect, it } from 'vitest';
import { maskInlineSpoilers } from './spoilers';

const M = '[spoiler]';

describe('maskInlineSpoilers', () => {
  it.each([
    ['a >!b!< c', `a ${M} c`],
    ['>!one!< and >!two!<', `${M} and ${M}`],
    ['line >!across\na break!< end', `line ${M} end`],
    ['no >!blank\n\nline!< here', 'no >!blank\n\nline!< here'],
    ['para >!a\n  \nb!< then >!c!<', `para >!a\n  \nb!< then ${M}`],
    ['unclosed >!forever', 'unclosed >!forever'],
    ['empty >!!< stays', 'empty >!!< stays'],
    ['>!!<x!<', M],
    ['plain text', 'plain text'],
  ])('%j', (input, expected) => {
    expect(maskInlineSpoilers(input, M)).toBe(expected);
  });

  it('stays linear on many unclosed openers', () => {
    const body = '>!a '.repeat(10_000);
    const start = performance.now();
    expect(maskInlineSpoilers(body, M)).toBe(body);
    expect(maskInlineSpoilers(`${body}>!x!<`, M)).toBe(M);
    expect(performance.now() - start).toBeLessThan(50);
  });
});

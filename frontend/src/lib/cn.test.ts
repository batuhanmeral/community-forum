import { describe, it, expect } from 'vitest';
import { cn } from './cn';

describe('cn', () => {
  it.each([
    [['a', false, null, undefined, 'b'], 'a b'],
    [[false, null, undefined], ''],
  ] as const)('cn(%j) -> %j', (classes, expected) => {
    expect(cn(...classes)).toBe(expected);
  });
});

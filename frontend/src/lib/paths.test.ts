import { describe, it, expect } from 'vitest';
import { userPath } from './paths';

describe('userPath', () => {
  it('encodes reserved characters', () => {
    expect(userPath('we ird/name')).toBe('/u/we%20ird%2Fname');
    expect(userPath('a.b+c@d')).toBe('/u/a.b%2Bc%40d');
    expect(userPath('alice')).toBe('/u/alice');
  });
});

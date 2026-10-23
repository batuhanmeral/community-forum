import { describe, expect, it } from 'vitest';
import { fieldErrors } from './apiErrors';

const axiosError = (status: number, data: unknown) => ({ response: { status, data } });

describe('fieldErrors', () => {
  it('returns the first message per field', () => {
    expect(
      fieldErrors(axiosError(400, { bio: ['Too long.', 'x'], avatar: 'Bad image.' })),
    ).toEqual({ bio: 'Too long.', avatar: 'Bad image.' });
  });

  it('keeps non-field keys for the caller to pick', () => {
    expect(fieldErrors(axiosError(400, { detail: 'Nope.' }))).toEqual({ detail: 'Nope.' });
  });

  it('ignores anything that is not a 400 with an object body', () => {
    expect(fieldErrors(axiosError(500, { bio: ['x'] }))).toEqual({});
    expect(fieldErrors(axiosError(400, '<html>'))).toEqual({});
    expect(fieldErrors(axiosError(400, ['x']))).toEqual({});
    expect(fieldErrors(axiosError(400, null))).toEqual({});
    expect(fieldErrors(new Error('x'))).toEqual({});
    expect(fieldErrors(null)).toEqual({});
  });
});

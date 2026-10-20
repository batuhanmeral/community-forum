/** Builds an unsigned JWT-shaped token; the frontend only ever reads its payload. */
export function fakeJwt(payload: object): string {
  const encode = (part: object) =>
    btoa(JSON.stringify(part)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  return `${encode({ alg: 'HS256', typ: 'JWT' })}.${encode(payload)}.sig`;
}

// @vitest-environment node
import { describe, it, expect } from 'vitest';
import { ESLint } from 'eslint';
import { fileURLToPath } from 'node:url';

const SVG_MESSAGE = 'Use a lucide-react icon instead of an inline <svg>.';
const GLYPH_MESSAGE = 'Use a lucide-react icon instead of an emoji or arrow glyph.';

const eslint = new ESLint({ cwd: fileURLToPath(new URL('../..', import.meta.url)) });

export async function lint(code: string, filePath = 'src/pages/__Probe.tsx'): Promise<string[]> {
  const [result] = await eslint.lintText(code, { filePath });
  return result.messages.filter((m) => m.ruleId === 'no-restricted-syntax').map((m) => m.message);
}

describe('icon lint rules', () => {
  it('inline <svg> is not allowed in components', async () => {
    expect(await lint('export const X = () => <svg viewBox="0 0 1 1" />;')).toContain(SVG_MESSAGE);
  });

  it('emoji and arrow glyphs are not allowed in JSX', async () => {
    expect(await lint('export const X = () => <span>💬</span>;')).toContain(GLYPH_MESSAGE);
    expect(await lint('export const X = () => <span>↑ 3</span>;')).toContain(GLYPH_MESSAGE);
    expect(await lint("export const X = () => <span>{ok ? '✓' : null}</span>;")).toContain(GLYPH_MESSAGE);
  });

  it('keyboard hint and middle dot stay allowed', async () => {
    expect(await lint('export const X = () => <span>⌘ K · go</span>;')).toEqual([]);
  });

  it('test files are exempt', async () => {
    expect(await lint('export const X = () => <svg />;', 'src/pages/Foo.test.tsx')).toEqual([]);
  });
});

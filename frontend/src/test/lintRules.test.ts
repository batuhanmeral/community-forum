// @vitest-environment node
/// <reference types="node" />
import { describe, it, expect } from 'vitest';
import { ESLint } from 'eslint';
import { fileURLToPath } from 'node:url';

const SVG_MESSAGE = 'Use a lucide-react icon instead of an inline <svg>.';
const GLYPH_MESSAGE = 'Use a lucide-react icon instead of an emoji or arrow glyph.';

const COLOUR_MESSAGE =
  'Use a design token (var(--color-*)) instead of a hard-coded colour, gradient or blur.';

const I18N_MESSAGE = 'Use t() with an i18n key instead of hard-coded UI text.';

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
    expect(await lint('export const X = () => <span>⌘ K · {x}</span>;')).toEqual([]);
  });

  it('test files are exempt', async () => {
    expect(await lint('export const X = () => <svg />;', 'src/pages/Foo.test.tsx')).toEqual([]);
  });
});

describe('colour lint rules', () => {
  it.each([
    'export const X = () => <div className="bg-[#123456]" />;',
    'export const X = () => <div className="bg-[#fff]" />;',
    'export const X = () => <div className="bg-[rgba(1,2,3,0.5)]" />;',
    "export const X = () => <div style={{ background: 'linear-gradient(1deg, red, blue)' }} />;",
    'export const X = () => <div className="backdrop-blur-xl" />;',
    'export const X = () => <div className="shadow-2xl" />;',
    'export const X = () => <div className="hover:shadow-xl" />;',
    'export const X = () => <div className="shadow-[0_1px_0_#000]" />;',
    'export const X = () => <div className={`a ${b} bg-[#123456]`} />;',
  ])('hard-coded colours and effects are rejected: %s', async (code) => {
    expect(await lint(code)).toContain(COLOUR_MESSAGE);
  });

  it('light shadows are allowed', async () => {
    expect(await lint('export const X = () => <div className="shadow-md shadow-sm" />;')).toEqual([]);
  });

  it('token references are allowed', async () => {
    expect(await lint('export const X = () => <div className="bg-[var(--color-bg-3)]" />;')).toEqual([]);
  });

  it('href anchors and ids are allowed', async () => {
    expect(await lint('export const X = () => <a href="#add">x</a>;')).toEqual([]);
    expect(await lint('export const X = () => <a href="/p/1#comments">x</a>;')).toEqual([]);
    expect(await lint("export const X = () => <a href={'#bad'}>x</a>;")).toEqual([]);
    expect(await lint('export const X = () => <a href="#comments">x</a>;')).toEqual([]);
  });

  it('test files are exempt', async () => {
    expect(await lint('export const X = () => <div className="bg-[#123456]" />;', 'src/pages/Foo.test.tsx')).toEqual([]);
  });
});

describe('i18n lint rules', () => {
  it.each([
    'export const X = () => <p>Hello world</p>;',
    'export const X = () => <input placeholder="Search" />;',
    "export const X = ({ a }) => <p>{a ? 'Loading…' : null}</p>;",
    "export const X = ({ a, b }) => <p>{a ? null : b ? 'Closed' : 'Open'}</p>;",
    "export const X = ({ a }) => <p>{a && 'Edited'}</p>;",
    "export const X = () => <button aria-label={'Close menu'} />;",
    'export const X = ({ a }) => <p>{`closes ${a}`}</p>;',
  ])('English UI text is rejected: %s', async (code) => {
    expect(await lint(code)).toContain(I18N_MESSAGE);
  });

  it.each([
    "export const X = () => <p>{t('home.empty')}</p>;",
    'export const X = () => <p>{count} · c/{slug}</p>;',
    "export const X = ({ a }) => <p>{t(a ? 'mod.status_open' : 'mod.status_closed')}</p>;",
    "export const X = ({ a }) => <p>{format(a ? 'Hello world' : 'Bye now')}</p>;",
    "export const X = ({ a }) => <Field label={a ? 'auth.username' : 'auth.email'} />;",
    "export const X = () => <input placeholder={t('nav.searchPlaceholder')} className=\"flex gap-2\" />;",
    "export const X = ({ a }) => <p className={a ? 'flex' : 'hidden'}>{a ? 'x' : null}</p>;",
    'export const X = () => <style>{`.live-dot { animation: pulse 2s infinite; }`}</style>;',
  ])('keys and data are allowed: %s', async (code) => {
    expect(await lint(code)).toEqual([]);
  });

  it('test files are exempt', async () => {
    expect(await lint('export const X = () => <p>Hello world</p>;', 'src/pages/Foo.test.tsx')).toEqual([]);
  });
});

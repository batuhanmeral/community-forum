import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readThemeChoice, setThemeChoice, startThemeSync } from './theme';

let prefersLight = false;
let listener: (() => void) | null = null;

beforeEach(() => {
  localStorage.clear();
  prefersLight = false;
  vi.stubGlobal('matchMedia', () => ({
    get matches() {
      return prefersLight;
    },
    addEventListener: (_: string, fn: () => void) => (listener = fn),
    removeEventListener: () => (listener = null),
  }));
});

afterEach(() => vi.unstubAllGlobals());

describe('theme', () => {
  it('defaults to following the system', () => {
    expect(readThemeChoice()).toBe('system');
  });

  it('applies and remembers an explicit choice', () => {
    setThemeChoice('light');
    expect(document.documentElement.dataset.theme).toBe('light');
    expect(readThemeChoice()).toBe('light');
    setThemeChoice('dark');
    expect(document.documentElement.dataset.theme).toBe('dark');
  });

  it('follows OS changes only while set to system', () => {
    const stop = startThemeSync();
    setThemeChoice('system');
    expect(document.documentElement.dataset.theme).toBe('dark');
    prefersLight = true;
    listener?.();
    expect(document.documentElement.dataset.theme).toBe('light');
    setThemeChoice('dark');
    listener?.();
    expect(document.documentElement.dataset.theme).toBe('dark');
    stop();
  });
});

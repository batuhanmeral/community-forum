import { describe, it, expect, vi, afterEach } from 'vitest';
import type { i18n as I18n } from 'i18next';

const LANG_KEY = 'nexus.lang';

afterEach(() => {
  localStorage.removeItem(LANG_KEY);
  vi.doUnmock('i18next');
});

describe('i18n startup', () => {
  it('sets <html lang> from the stored language at startup', async () => {
    localStorage.setItem(LANG_KEY, 'tr');
    document.documentElement.lang = '';
    // A fresh i18next instance stands in for a page load; the shared singleton keeps old listeners.
    vi.doMock('i18next', async () => {
      const actual = await vi.importActual<{ default: I18n }>('i18next');
      return { default: actual.default.createInstance() };
    });
    vi.resetModules();
    await import('@/i18n');
    expect(document.documentElement.lang).toBe('tr');
  });
});

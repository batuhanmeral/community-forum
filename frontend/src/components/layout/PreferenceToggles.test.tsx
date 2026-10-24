import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import i18n from '@/i18n';
import { resetLanguage } from '@/test/i18nHelpers';
import { LanguageToggle, ThemeToggle } from './PreferenceToggles';

describe('ThemeToggle', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal('matchMedia', () => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
    document.documentElement.dataset.theme = 'dark';
  });
  afterEach(() => vi.unstubAllGlobals());

  it('flips between dark and light and remembers the choice', async () => {
    render(<ThemeToggle />);
    await userEvent.click(screen.getByRole('button', { name: 'Switch to light theme' }));
    expect(document.documentElement.dataset.theme).toBe('light');
    expect(localStorage.getItem('nexus.theme')).toBe('light');

    await userEvent.click(screen.getByRole('button', { name: 'Switch to dark theme' }));
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(localStorage.getItem('nexus.theme')).toBe('dark');
  });
});

describe('LanguageToggle', () => {
  afterEach(resetLanguage);

  it('switches between English and Turkish', async () => {
    render(<LanguageToggle />);
    expect(screen.getByRole('button')).toHaveTextContent('en');
    await userEvent.click(screen.getByRole('button', { name: 'Switch language to Türkçe' }));
    expect(i18n.language).toBe('tr');
    await userEvent.click(screen.getByRole('button', { name: 'Dili English olarak değiştir' }));
    expect(i18n.language).toBe('en');
  });
});

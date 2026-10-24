import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Moon, Sun } from 'lucide-react';
import { LANGUAGES, type Language } from '@/i18n';
import { setThemeChoice } from '@/lib/theme';
import { cn } from '@/lib/cn';

const toggleClasses = cn(
  'grid h-[38px] min-w-[38px] place-items-center rounded-[11px] px-1.5',
  'text-[var(--color-text-soft)] transition hover:bg-[var(--color-bg-elevated)] hover:text-[var(--color-text)]',
);

// The applied theme, not the stored choice: "system" still renders as light or dark.
const appliedTheme = () => (document.documentElement.dataset.theme === 'light' ? 'light' : 'dark');

export function ThemeToggle() {
  const { t } = useTranslation();
  const [theme, setTheme] = useState(appliedTheme);
  const next = theme === 'light' ? 'dark' : 'light';
  const label = next === 'light' ? t('nav.switchToLight') : t('nav.switchToDark');

  function toggle() {
    setThemeChoice(next);
    setTheme(next);
  }

  return (
    <button type="button" onClick={toggle} title={label} aria-label={label} className={toggleClasses}>
      {theme === 'light' ? <Moon className="h-[18px] w-[18px]" /> : <Sun className="h-[18px] w-[18px]" />}
    </button>
  );
}

export function LanguageToggle() {
  const { t, i18n } = useTranslation();
  const next = LANGUAGES.find((l) => l.code !== i18n.language) ?? LANGUAGES[0];
  const label = t('nav.switchLanguage', { language: next.label });

  return (
    <button
      type="button"
      onClick={() => i18n.changeLanguage(next.code satisfies Language)}
      title={label}
      aria-label={label}
      className={cn(toggleClasses, 'font-mono text-[12px] font-semibold uppercase')}
    >
      {i18n.language}
    </button>
  );
}

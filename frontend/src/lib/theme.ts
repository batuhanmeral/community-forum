export type ThemeChoice = 'system' | 'light' | 'dark';

const THEME_KEY = 'nexus.theme';
const lightQuery = () => window.matchMedia('(prefers-color-scheme: light)');

export function readThemeChoice(): ThemeChoice {
  const stored = localStorage.getItem(THEME_KEY);
  return stored === 'light' || stored === 'dark' ? stored : 'system';
}

function apply(choice: ThemeChoice) {
  const light = choice === 'light' || (choice === 'system' && lightQuery().matches);
  document.documentElement.dataset.theme = light ? 'light' : 'dark';
}

export function setThemeChoice(choice: ThemeChoice) {
  if (choice === 'system') localStorage.removeItem(THEME_KEY);
  else localStorage.setItem(THEME_KEY, choice);
  apply(choice);
}

/** Keeps "system" in step with the OS setting while the app is open. */
export function startThemeSync(): () => void {
  const query = lightQuery();
  const onChange = () => {
    if (readThemeChoice() === 'system') apply('system');
  };
  query.addEventListener('change', onChange);
  return () => query.removeEventListener('change', onChange);
}

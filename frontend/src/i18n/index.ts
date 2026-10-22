import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import { en } from './en';
import { tr } from './tr';

const LANG_KEY = 'nexus.lang';

export type Language = 'en' | 'tr';
export const LANGUAGES: { code: Language; label: string }[] = [
  { code: 'en', label: 'English' },
  { code: 'tr', label: 'Türkçe' },
];

const stored = localStorage.getItem(LANG_KEY);

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    tr: { translation: tr },
  },
  lng: stored === 'tr' || stored === 'en' ? stored : 'en',
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
});

// Inline resources make init synchronous, so the startup language never reaches the listener below.
document.documentElement.lang = i18n.language;

i18n.on('languageChanged', (lng) => {
  localStorage.setItem(LANG_KEY, lng);
  document.documentElement.lang = lng;
});

export default i18n;

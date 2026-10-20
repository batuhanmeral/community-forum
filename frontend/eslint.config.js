import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export const SVG_MESSAGE = 'Use a lucide-react icon instead of an inline <svg>.';
export const GLYPH_MESSAGE =
  'Use a lucide-react icon instead of an emoji or arrow glyph.';

// Emoji, arrows, dingbats and symbol blocks; keeps ⌘ (U+2318) and · allowed.
const GLYPH_RANGE = '[←-⇿☀-➿⬀-⯿\\u{1F300}-\\u{1FAFF}]';

// Selector lists are spread into ONE no-restricted-syntax value so later tasks append here.
export const ICON_SELECTORS = [
  { selector: "JSXOpeningElement[name.name='svg']", message: SVG_MESSAGE },
  { selector: `JSXText[value=/${GLYPH_RANGE}/u]`, message: GLYPH_MESSAGE },
  { selector: `Literal[value=/${GLYPH_RANGE}/u]`, message: GLYPH_MESSAGE },
  { selector: `TemplateElement[value.raw=/${GLYPH_RANGE}/u]`, message: GLYPH_MESSAGE },
];

export const RESTRICTED_SYNTAX = [...ICON_SELECTORS];

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
    },
    rules: {
      // This codebase intentionally sets loading/reset state synchronously inside
      // effects; the v7 recommended rule flags that pervasive, deliberate pattern.
      'react-hooks/set-state-in-effect': 'off',
    },
  },
  {
    files: ['src/**/*.tsx'],
    ignores: ['src/**/*.test.tsx', 'src/test/**'],
    rules: {
      'no-restricted-syntax': ['error', ...RESTRICTED_SYNTAX],
    },
  },
])

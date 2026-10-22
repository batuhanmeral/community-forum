import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export const SVG_MESSAGE = 'Use a lucide-react icon instead of an inline <svg>.';
export const GLYPH_MESSAGE =
  'Use a lucide-react icon instead of an emoji or arrow glyph.';

export const COLOUR_MESSAGE =
  'Use a design token (var(--color-*)) instead of a hard-coded colour, gradient or blur.';

// Hex colours need a colour-like context so href anchors such as "#add" stay allowed.
const COLOUR_PATTERN =
  '(?:^|(?<=[\\[\\s(,:]))#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6})\\b|(?<=[\\[\\s(,:])#[0-9a-fA-F]{3,4}\\b|rgba?\\(|hsla?\\(|gradient\\(|backdrop-blur|accent-glow|(?<![\\w-])shadow-(?:lg|xl|2xl|\\[)';

// Emoji, arrows, dingbats and symbol blocks; keeps ⌘ (U+2318) and · allowed.
const GLYPH_RANGE = '[←-⇿☀-➿⬀-⯿\\u{1F300}-\\u{1FAFF}]';

// Selector lists are spread into ONE no-restricted-syntax value so later tasks append here.
export const ICON_SELECTORS = [
  { selector: "JSXOpeningElement[name.name='svg']", message: SVG_MESSAGE },
  { selector: `JSXText[value=/${GLYPH_RANGE}/u]`, message: GLYPH_MESSAGE },
  { selector: `Literal[value=/${GLYPH_RANGE}/u]`, message: GLYPH_MESSAGE },
  { selector: `TemplateElement[value.raw=/${GLYPH_RANGE}/u]`, message: GLYPH_MESSAGE },
];

export const COLOUR_SELECTORS = [
  { selector: `Literal[value=/${COLOUR_PATTERN}/]`, message: COLOUR_MESSAGE },
  { selector: `TemplateElement[value.raw=/${COLOUR_PATTERN}/]`, message: COLOUR_MESSAGE },
];

export const I18N_MESSAGE = 'Use t() with an i18n key instead of hard-coded UI text.';

// UI text has at least two letters; i18n keys such as 'mod.status_open' stay allowed.
const TWO_LETTERS = '/\\p{L}[\\s\\S]*\\p{L}/u';
const I18N_KEY = '/^[a-z][A-Za-z]*(\\.[A-Za-z0-9_]+)+$/';
const UI_TEXT = `[value=${TWO_LETTERS}]:not([value=${I18N_KEY}])`;
const UI_TEMPLATE_TEXT = `[value.raw=${TWO_LETTERS}]`;
const TEXT_ATTRIBUTE = 'JSXAttribute[name.name=/^(?:placeholder|title|aria-label|alt|label)$/]';
const BRANCH = ':matches(ConditionalExpression, LogicalExpression)';
const MAX_BRANCH_DEPTH = 3;

// A rendered string sits in the container itself or in nested conditional/logical branches; call arguments are not reached.
function renderedStrings(container) {
  return Array.from({ length: MAX_BRANCH_DEPTH + 1 }, (_, depth) => {
    const position = [container, ...Array(depth).fill(BRANCH)].join(' > ');
    return [`${position} > Literal${UI_TEXT}`, `${position} > TemplateLiteral > TemplateElement${UI_TEMPLATE_TEXT}`];
  }).flat();
}

export const I18N_SELECTORS = [
  `JSXText${UI_TEXT}`,
  `${TEXT_ATTRIBUTE} > Literal${UI_TEXT}`,
  // CSS inside <style> is not UI text.
  ...renderedStrings(":matches(JSXElement:not([openingElement.name.name='style']), JSXFragment) > JSXExpressionContainer"),
  ...renderedStrings(`${TEXT_ATTRIBUTE} > JSXExpressionContainer`),
].map((selector) => ({ selector, message: I18N_MESSAGE }));

export const RESTRICTED_SYNTAX = [...ICON_SELECTORS, ...COLOUR_SELECTORS, ...I18N_SELECTORS];

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

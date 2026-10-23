import { cleanup } from '@testing-library/react';
import i18n from '@/i18n';

const TEXT_ATTRIBUTES = ['aria-label', 'title', 'placeholder', 'alt'];

// Text a user can read or hear: each text node plus the attributes that carry copy, space-joined so \b works.
export function visibleText(root: Element = document.body): string {
  const parts: string[] = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) parts.push(node.textContent ?? '');
  const selector = TEXT_ATTRIBUTES.map((a) => `[${a}]`).join(',');
  root.querySelectorAll(selector).forEach((el) => {
    TEXT_ATTRIBUTES.forEach((a) => parts.push(el.getAttribute(a) ?? ''));
  });
  return parts.join(' ');
}

// Unmount first so switching back to English does not re-render a mounted tree outside act().
export async function resetLanguage(): Promise<void> {
  cleanup();
  await i18n.changeLanguage('en');
}

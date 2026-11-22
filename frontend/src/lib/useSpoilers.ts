import { useCallback, useEffect, useState, type KeyboardEvent, type MouseEvent } from 'react';
import { useTranslation } from 'react-i18next';

const SELECTOR = 'span.spoiler';
const REVEALED = 'spoiler-revealed';

function reveal(el: Element) {
  el.classList.add(REVEALED);
  el.setAttribute('aria-expanded', 'true');
  el.removeAttribute('aria-label');
  el.removeAttribute('role');
  el.removeAttribute('tabindex');
}

/**
 * Server-rendered `>!text!<` arrives as `<span class="spoiler">`. This makes each one a
 * keyboard-reachable control that stays hidden until activated (Enter, Space or click).
 * Returns `[ref, onClick, onKeyDown]` for the element holding the HTML.
 */
export function useSpoilers(html: string) {
  const { t } = useTranslation();
  // A callback ref, so the effect re-runs once the element actually exists.
  const [node, attach] = useState<HTMLElement | null>(null);

  useEffect(() => {
    node?.querySelectorAll(SELECTOR).forEach((el) => {
      if (el.classList.contains(REVEALED)) return;
      el.setAttribute('role', 'button');
      el.setAttribute('tabindex', '0');
      el.setAttribute('aria-expanded', 'false');
      el.setAttribute('aria-label', t('spoiler.hiddenText'));
    });
  }, [node, html, t]);

  const onClick = useCallback((e: MouseEvent<HTMLElement>) => {
    const el = (e.target as Element).closest(SELECTOR);
    if (el && !el.classList.contains(REVEALED)) {
      e.preventDefault();
      reveal(el);
    }
  }, []);

  const onKeyDown = useCallback((e: KeyboardEvent<HTMLElement>) => {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    const el = (e.target as Element).closest(SELECTOR);
    if (el && !el.classList.contains(REVEALED)) {
      e.preventDefault();
      reveal(el);
    }
  }, []);

  return [attach, onClick, onKeyDown] as const;
}

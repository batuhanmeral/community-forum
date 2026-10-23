import { useCallback, type MouseEvent } from 'react';
import { useNavigate } from 'react-router-dom';

// Server-rendered markdown links (e.g. @mentions) to in-app paths would otherwise reload the SPA.
export function useInternalLinkClick() {
  const navigate = useNavigate();
  return useCallback(
    (e: MouseEvent<HTMLElement>) => {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const href = (e.target as Element).closest('a')?.getAttribute('href');
      if (!href?.startsWith('/') || href.startsWith('//')) return;
      e.preventDefault();
      navigate(href);
    },
    [navigate],
  );
}

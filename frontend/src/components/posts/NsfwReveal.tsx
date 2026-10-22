import { useRef, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/cn';

export function NsfwReveal({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const [revealed, setRevealed] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  function reveal() {
    // The button unmounts on reveal; focusing the wrapper first keeps keyboard focus off <body>.
    wrapperRef.current?.focus();
    setRevealed(true);
  }

  return (
    <div
      ref={wrapperRef}
      tabIndex={-1}
      className="relative w-full outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--color-link)]"
    >
      <div aria-hidden={revealed ? undefined : true} className={cn(!revealed && 'pointer-events-none blur-2xl')}>
        {children}
      </div>
      {!revealed && (
        // z-10 lifts the button above a parent card's stretched-link overlay
        <button
          type="button"
          onClick={reveal}
          className="absolute inset-0 z-10 grid cursor-pointer place-items-center text-sm font-semibold text-[var(--color-text)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-link)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg)]"
        >
          <span className="rounded-full bg-[var(--color-bg-elevated)] px-4 py-2">{t('nsfw.reveal')}</span>
        </button>
      )}
    </div>
  );
}

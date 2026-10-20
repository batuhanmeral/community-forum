import { useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/cn';

export function NsfwReveal({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const [revealed, setRevealed] = useState(false);

  return (
    <div className="relative w-full">
      <div aria-hidden={revealed ? undefined : true} className={cn(!revealed && 'pointer-events-none blur-2xl')}>
        {children}
      </div>
      {!revealed && (
        // z-10 lifts the button above a parent card's stretched-link overlay
        <button
          type="button"
          onClick={() => setRevealed(true)}
          className="absolute inset-0 z-10 grid cursor-pointer place-items-center text-sm font-semibold text-[var(--color-text)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg)]"
        >
          <span className="rounded-full bg-[var(--color-bg-elevated)] px-4 py-2">{t('nsfw.reveal')}</span>
        </button>
      )}
    </div>
  );
}

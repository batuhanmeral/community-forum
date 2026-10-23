import { useEffect } from 'react';
import { Link, useRouteError } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button, buttonClasses } from '@/components/ui/Button';
import { PageTitle } from '@/components/ui/PageTitle';

export const CHUNK_RELOAD_KEY = 'nexus.chunkReloadAt';
export const CHUNK_RELOAD_COOLDOWN_MS = 30_000;

const CHUNK_ERROR_PATTERN =
  /dynamically imported module|Importing a module script failed|error loading dynamically imported module/i;

// Kept beside the component it serves; the brief fixes this export location.
// eslint-disable-next-line react-refresh/only-export-components
export function isChunkLoadError(error: unknown): boolean {
  if (!(error instanceof Error)) return false;
  return (
    error.name === 'ChunkLoadError' ||
    (error instanceof TypeError && CHUNK_ERROR_PATTERN.test(error.message))
  );
}

// Returns true when a reload was triggered; the timestamp stops an endless reload loop.
function reloadOnceForStaleChunk(): boolean {
  try {
    const last = Number(sessionStorage.getItem(CHUNK_RELOAD_KEY));
    if (last && Date.now() - last < CHUNK_RELOAD_COOLDOWN_MS) return false;
    sessionStorage.setItem(CHUNK_RELOAD_KEY, String(Date.now()));
  } catch {
    // Storage blocked (private mode): without a guard a reload could loop, so show the screen.
    return false;
  }
  window.location.reload();
  return true;
}

export function RouteErrorPage() {
  const { t } = useTranslation();
  const error = useRouteError();
  const chunkError = isChunkLoadError(error);

  useEffect(() => {
    if (chunkError) reloadOnceForStaleChunk();
  }, [chunkError]);

  return (
    <div className="flex flex-col items-center gap-4 py-24 text-center">
      <PageTitle title={t('errors.title')} />
      <h1 className="text-2xl font-bold tracking-tight">{t('errors.title')}</h1>
      <p className="text-[var(--color-text-muted)]">{t('errors.body')}</p>
      <div className="flex gap-3">
        <Button onClick={() => window.location.reload()}>{t('errors.retry')}</Button>
        <Link
          to="/"
          className={buttonClasses({ variant: 'secondary' })}
        >
          {t('errors.home')}
        </Link>
      </div>
    </div>
  );
}

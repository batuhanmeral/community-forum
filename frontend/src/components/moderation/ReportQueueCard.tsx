import { useCallback, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  dismissReport,
  listModReports,
  resolveReport,
  type Report,
  type ReportStatus,
} from '@/api/moderation';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { usePagedList } from '@/lib/usePagedList';
import { timeAgo } from '@/lib/time';
import { cn } from '@/lib/cn';

const STATUSES: ReportStatus[] = ['open', 'resolved', 'dismissed'];

export function ReportQueueCard({ slug }: { slug: string }) {
  const { t } = useTranslation();
  const [status, setStatus] = useState<ReportStatus>('open');
  const fetchPage = useCallback(
    (page: number) => listModReports(slug, status, page),
    [slug, status],
  );
  const { items, loading, loadFailed, nextPage, loadMore, loadMoreFailed, remove } = usePagedList(fetchPage);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function act(id: number, kind: 'resolve' | 'dismiss') {
    setBusyId(id);
    setError(null);
    try {
      if (kind === 'resolve') await resolveReport(slug, id);
      else await dismissReport(slug, id);
      remove(id);
    } catch {
      setError(t('mod.actionFailed'));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-semibold tracking-tight">{t('mod.reportsTitle')}</h2>
        <div className="flex gap-0.5 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-1)] p-1">
          {STATUSES.map((s) => (
            <button
              key={s}
              type="button"
              aria-pressed={status === s}
              onClick={() => setStatus(s)}
              className={cn(
                'rounded-full px-3.5 py-1.5 text-[13px] font-medium transition',
                status === s
                  ? 'bg-[var(--color-bg-3)] text-[var(--color-text)]'
                  : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]',
              )}
            >
              {t(`mod.status_${s}`)}
            </button>
          ))}
        </div>
      </div>
      {error && <p className="mt-2 text-sm text-[var(--color-danger)]">{error}</p>}
      <div className="mt-4 flex flex-col gap-2.5">
        {loading ? (
          <p className="text-sm text-[var(--color-text-muted)]">{t('mod.loading')}</p>
        ) : loadFailed ? (
          <p className="text-sm text-[var(--color-danger)]">{t('mod.loadFailed')}</p>
        ) : items.length === 0 ? (
          <p className="text-sm text-[var(--color-text-muted)]">{t('mod.reportsEmpty')}</p>
        ) : (
          items.map((r) => (
            <ReportRow key={r.id} report={r} busy={busyId === r.id} onAct={act} />
          ))
        )}
      </div>
      {nextPage !== null && (
        <button
          type="button"
          onClick={loadMore}
          className="mt-3 text-sm text-[var(--color-accent)] hover:underline"
        >
          {t('mod.loadMore')}
        </button>
      )}
      {loadMoreFailed && (
        <p className="mt-2 text-sm text-[var(--color-danger)]">{t('mod.loadMoreFailed')}</p>
      )}
    </Card>
  );
}

interface ReportRowProps {
  report: Report;
  busy: boolean;
  onAct: (id: number, kind: 'resolve' | 'dismiss') => void;
}

function ReportRow({ report: r, busy, onAct }: ReportRowProps) {
  const { t } = useTranslation();
  const preview = r.target_preview;
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 rounded-[12px] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-4 py-3">
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex flex-wrap items-center gap-2 text-[11.5px] text-[var(--color-text-dim)]">
          <span className="rounded-full border border-[var(--color-border)] bg-[var(--color-bg-3)] px-2 py-0.5 text-[var(--color-text-soft)]">
            {t(`mod.target_${r.target_type}`)}
          </span>
          <span>{timeAgo(r.created_at)}</span>
        </div>
        {preview ? (
          <p className="flex min-w-0 items-baseline gap-1 text-sm">
            <Link
              to={preview.link}
              className="truncate text-[var(--color-accent)] hover:underline"
            >
              {preview.text}
            </Link>
            {preview.is_deleted && (
              <span className="shrink-0 text-[var(--color-text-muted)]">
                ({t('mod.targetDeleted')})
              </span>
            )}
          </p>
        ) : (
          <p className="text-sm italic text-[var(--color-text-muted)]">{t('mod.targetGone')}</p>
        )}
        <p className="mt-1 text-sm text-[var(--color-text-soft)]">{r.reason}</p>
      </div>
      {r.status === 'open' && (
        <div className="flex shrink-0 gap-2">
          <Button variant="secondary" size="sm" loading={busy} onClick={() => onAct(r.id, 'dismiss')}>
            {t('mod.dismiss')}
          </Button>
          <Button size="sm" loading={busy} onClick={() => onAct(r.id, 'resolve')}>
            {t('mod.resolve')}
          </Button>
        </div>
      )}
    </div>
  );
}

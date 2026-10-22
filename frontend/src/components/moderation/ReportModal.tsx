import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { reportContent, type ReportTarget } from '@/api/moderation';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/cn';

interface ReportModalProps {
  open: boolean;
  onClose: () => void;
  target: ReportTarget;
  objectId: number;
  label?: string;
}

// The value is what moderators receive (the backend and queue are English); the key is what the reporter reads.
const REASONS = [
  { value: 'Spam', key: 'report.reason_spam' },
  { value: 'Harassment or bullying', key: 'report.reason_harassment' },
  { value: 'Hate speech', key: 'report.reason_hate' },
  { value: 'Violence or threats', key: 'report.reason_violence' },
  { value: 'Misinformation', key: 'report.reason_misinformation' },
  { value: 'NSFW content not tagged', key: 'report.reason_nsfw' },
  { value: 'Other', key: 'report.reason_other' },
];

export function ReportModal({ open, onClose, target, objectId, label }: ReportModalProps) {
  const { t } = useTranslation();
  const [reason, setReason] = useState('');
  const [detail, setDetail] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setReason('');
      setDetail('');
      setSubmitting(false);
      setDone(false);
      setError(null);
    }
  }, [open]);

  async function handleSubmit() {
    if (!reason || submitting) return;
    // Combine the chosen reason with the optional free-text detail (max 255 server-side).
    const full = detail.trim() ? `${reason}: ${detail.trim()}` : reason;
    setSubmitting(true);
    setError(null);
    try {
      await reportContent(target, objectId, full.slice(0, 255));
      setDone(true);
    } catch (e) {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        t('report.failed');
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  const targetLabel = label ?? t(`report.target_${target}`);

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={done ? t('report.submitted') : t('report.title', { target: targetLabel })}
      footer={
        done ? (
          <Button variant="secondary" onClick={onClose}>
            {t('common.close')}
          </Button>
        ) : (
          <>
            <Button variant="secondary" onClick={onClose}>
              {t('common.cancel')}
            </Button>
            <Button variant="danger" onClick={handleSubmit} loading={submitting} disabled={!reason}>
              {t('report.submit')}
            </Button>
          </>
        )
      }
    >
      {done ? (
        <p className="text-sm text-[var(--color-text-muted)]">
          {t('report.thanks')}
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-[var(--color-text-muted)]">
            {t('report.question', { target: targetLabel })}
          </p>
          <div className="flex flex-col gap-1.5">
            {REASONS.map((r) => (
              <button
                key={r.value}
                type="button"
                onClick={() => setReason(r.value)}
                className={cn(
                  'rounded-[10px] border px-3 py-2 text-left text-sm transition',
                  reason === r.value
                    ? 'border-[var(--color-accent)] bg-[var(--color-accent-dim)] text-[var(--color-text)]'
                    : 'border-[var(--color-border)] bg-[var(--color-bg-elevated)] text-[var(--color-text-soft)] hover:border-[var(--color-border-strong)]',
                )}
              >
                {t(r.key)}
              </button>
            ))}
          </div>
          <textarea
            rows={3}
            value={detail}
            onChange={(e) => setDetail(e.target.value)}
            placeholder={t('report.contextPlaceholder')}
            className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-2 text-sm focus:border-[var(--color-accent)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]/30"
          />
          {error && <p className="text-sm text-[var(--color-danger)]">{error}</p>}
        </div>
      )}
    </Modal>
  );
}

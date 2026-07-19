import { useEffect, useState } from 'react';
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

const REASONS = [
  'Spam',
  'Harassment or bullying',
  'Hate speech',
  'Violence or threats',
  'Misinformation',
  'NSFW content not tagged',
  'Other',
];

export function ReportModal({ open, onClose, target, objectId, label }: ReportModalProps) {
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
        'Could not submit report. You may have already reported this recently.';
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  const targetLabel = label ?? target;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={done ? 'Report submitted' : `Report ${targetLabel}`}
      footer={
        done ? (
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
        ) : (
          <>
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button variant="danger" onClick={handleSubmit} loading={submitting} disabled={!reason}>
              Submit report
            </Button>
          </>
        )
      }
    >
      {done ? (
        <p className="text-sm text-[var(--color-text-muted)]">
          Thanks for keeping the community safe. Moderators will review this report.
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-[var(--color-text-muted)]">
            Why are you reporting this {targetLabel}?
          </p>
          <div className="flex flex-col gap-1.5">
            {REASONS.map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => setReason(r)}
                className={cn(
                  'rounded-[10px] border px-3 py-2 text-left text-sm transition',
                  reason === r
                    ? 'border-[var(--color-accent)] bg-[var(--color-accent-dim)] text-[var(--color-text)]'
                    : 'border-[var(--color-border)] bg-[var(--color-bg-elevated)] text-[var(--color-text-soft)] hover:border-[var(--color-border-strong)]',
                )}
              >
                {r}
              </button>
            ))}
          </div>
          <textarea
            rows={3}
            value={detail}
            onChange={(e) => setDetail(e.target.value)}
            placeholder="Add more context (optional)…"
            className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-2 text-sm focus:border-[var(--color-accent)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]/30"
          />
          {error && <p className="text-sm text-[var(--color-danger)]">{error}</p>}
        </div>
      )}
    </Modal>
  );
}

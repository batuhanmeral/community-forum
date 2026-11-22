import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { listRemovalReasons, type RemovalChoice, type RemovalReason } from '@/api/moderation';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';

interface Props {
  open: boolean;
  slug: string;
  /** The community requires a reason for moderator removals. */
  required: boolean;
  onClose: () => void;
  onConfirm: (choice: RemovalChoice) => Promise<void>;
}

export function RemovalReasonModal({ open, slug, required, onClose, onConfirm }: Props) {
  const { t } = useTranslation();
  const [reasons, setReasons] = useState<RemovalReason[]>([]);
  const [reason, setReason] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setReason('');
    setNote('');
    setError(false);
    listRemovalReasons(slug)
      .then((r) => !cancelled && setReasons(r))
      .catch(() => !cancelled && setReasons([]));
    return () => {
      cancelled = true;
    };
  }, [open, slug]);

  async function submit() {
    if (busy || (required && reason === '')) return;
    setBusy(true);
    setError(false);
    try {
      await onConfirm({ reason: reason === '' ? null : Number(reason), note: note.trim() });
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  }

  const chosen = reasons.find((r) => String(r.id) === reason);

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t('mod.removeTitle')}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t('mod.cancel')}
          </Button>
          <Button variant="danger" loading={busy} disabled={required && reason === ''} onClick={submit}>
            {t('mod.remove')}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="removal-reason"
            className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-muted)]"
          >
            {t('mod.removalReason')}
          </label>
          <select
            id="removal-reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-2 text-sm text-[var(--color-text)]"
          >
            <option value="">{t('mod.removalNoReason')}</option>
            {reasons.map((r) => (
              <option key={r.id} value={r.id}>
                {r.title}
              </option>
            ))}
          </select>
          {chosen && <p className="text-xs text-[var(--color-text-muted)]">{chosen.body}</p>}
        </div>
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="removal-note"
            className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-muted)]"
          >
            {t('mod.removalNote')}
          </label>
          <textarea
            id="removal-note"
            rows={2}
            maxLength={500}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-2 text-sm text-[var(--color-text)]"
          />
        </div>
        {error && (
          <p role="alert" className="text-sm text-[var(--color-danger)]">
            {t('mod.removeFailed')}
          </p>
        )}
      </div>
    </Modal>
  );
}

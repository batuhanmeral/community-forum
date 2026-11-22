import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { createModmailThread } from '@/api/modmail';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';

interface Props {
  open: boolean;
  slug: string;
  onClose: () => void;
}

export function NewModmailModal({ open, slug, onClose }: Props) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (busy || !subject.trim() || !body.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const thread = await createModmailThread(slug, subject.trim(), body.trim());
      onClose();
      setSubject('');
      setBody('');
      navigate(`/modmail/${thread.id}`);
    } catch (err) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      setError(status === 429 ? t('modmail.rateLimited') : t('modmail.sendFailed'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t('modmail.newTitle', { slug })}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button loading={busy} disabled={!subject.trim() || !body.trim()} onClick={submit}>
            {t('modmail.send')}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <Input
          name="modmail-subject"
          label={t('modmail.subject')}
          value={subject}
          maxLength={100}
          onChange={(e) => setSubject(e.target.value)}
        />
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="modmail-body"
            className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-muted)]"
          >
            {t('modmail.message')}
          </label>
          <textarea
            id="modmail-body"
            rows={5}
            maxLength={5000}
            value={body}
            onChange={(e) => setBody(e.target.value)}
            className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-2 text-sm text-[var(--color-text)]"
          />
        </div>
        {error && (
          <p role="alert" className="text-sm text-[var(--color-danger)]">
            {error}
          </p>
        )}
      </div>
    </Modal>
  );
}

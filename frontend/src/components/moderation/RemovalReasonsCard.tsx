import { useEffect, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import {
  createRemovalReason,
  deleteRemovalReason,
  listRemovalReasons,
  type RemovalReason,
} from '@/api/moderation';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';

interface Props {
  slug: string;
  /** Admin-only: whether moderator removals must carry a reason. */
  required?: boolean;
  onRequiredChange?: (value: boolean) => Promise<void>;
}

export function RemovalReasonsCard({ slug, required, onRequiredChange }: Props) {
  const { t } = useTranslation();
  const [reasons, setReasons] = useState<RemovalReason[]>([]);
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    listRemovalReasons(slug)
      .then((r) => !cancelled && setReasons(r))
      .catch(() => !cancelled && setReasons([]));
    return () => {
      cancelled = true;
    };
  }, [slug]);

  async function guarded(action: () => Promise<void>) {
    setError(false);
    try {
      await action();
    } catch {
      setError(true);
    }
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!title.trim() || !body.trim() || busy) return;
    setBusy(true);
    await guarded(async () => {
      const created = await createRemovalReason(slug, title.trim(), body.trim());
      setReasons((arr) => [...arr, created]);
      setTitle('');
      setBody('');
    });
    setBusy(false);
  }

  return (
    <Card>
      <h2 className="text-base font-semibold tracking-tight">{t('mod.removalTitle')}</h2>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">{t('mod.removalHint')}</p>
      {onRequiredChange && (
        <label className="mt-3 flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={Boolean(required)}
            onChange={(e) => void guarded(() => onRequiredChange(e.target.checked))}
          />
          {t('mod.removalRequire')}
        </label>
      )}
      <ul className="mt-3 flex flex-col gap-2">
        {reasons.map((r) => (
          <li
            key={r.id}
            className="flex items-start justify-between gap-3 rounded-[12px] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-4 py-3"
          >
            <div className="min-w-0">
              <p className="text-sm font-medium">{r.title}</p>
              <p className="mt-0.5 whitespace-pre-wrap text-xs text-[var(--color-text-muted)]">{r.body}</p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              aria-label={t('mod.removalDeleteLabel', { reason: r.title })}
              onClick={() =>
                void guarded(async () => {
                  await deleteRemovalReason(slug, r.id);
                  setReasons((arr) => arr.filter((x) => x.id !== r.id));
                })
              }
            >
              {t('mod.delete')}
            </Button>
          </li>
        ))}
      </ul>
      <form onSubmit={handleCreate} className="mt-4 flex flex-col gap-3">
        <Input
          name="removal-title"
          label={t('mod.removalTitleField')}
          value={title}
          maxLength={60}
          onChange={(e) => setTitle(e.target.value)}
        />
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="removal-body"
            className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-muted)]"
          >
            {t('mod.removalBody')}
          </label>
          <textarea
            id="removal-body"
            rows={3}
            maxLength={1000}
            value={body}
            onChange={(e) => setBody(e.target.value)}
            className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-2 text-sm text-[var(--color-text)]"
          />
        </div>
        <div>
          <Button type="submit" loading={busy} disabled={!title.trim() || !body.trim()}>
            {t('mod.removalAdd')}
          </Button>
        </div>
      </form>
      {error && (
        <p role="alert" className="mt-2 text-sm text-[var(--color-danger)]">
          {t('mod.removalFailed')}
        </p>
      )}
    </Card>
  );
}

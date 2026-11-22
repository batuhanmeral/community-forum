import { useEffect, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import {
  assignUserFlair,
  createUserFlair,
  deleteUserFlair,
  listUserFlairs,
} from '@/api/communities';
import type { UserFlair } from '@/features/communities/types';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';

interface Props {
  slug: string;
  /** The caller may pick their own flair (moderator, or the community allows it). */
  canSelect: boolean;
  isModerator: boolean;
  /** Admin-only toggle: whether members may pick their own flair. */
  allowSelf?: boolean;
  onAllowSelfChange?: (value: boolean) => Promise<void>;
}

// Flair colours are user data, not theme colours; the picker needs a hex default.
// eslint-disable-next-line no-restricted-syntax
const DEFAULT_COLOR = '#888888';

export function UserFlairCard({ slug, canSelect, isModerator, allowSelf, onAllowSelfChange }: Props) {
  const { t } = useTranslation();
  const [flairs, setFlairs] = useState<UserFlair[]>([]);
  const [selected, setSelected] = useState('');
  const [text, setText] = useState('');
  const [color, setColor] = useState(DEFAULT_COLOR);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listUserFlairs(slug)
      .then((f) => !cancelled && setFlairs(f))
      .catch(() => !cancelled && setFlairs([]));
    return () => {
      cancelled = true;
    };
  }, [slug]);

  async function handleSelect(value: string) {
    setError(null);
    try {
      await assignUserFlair(slug, value === '' ? null : Number(value));
      setSelected(value);
    } catch {
      setError(t('mod.userFlairFailed'));
    }
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setError(null);
    try {
      const flair = await createUserFlair(slug, trimmed, color);
      setFlairs((arr) => [...arr, flair]);
      setText('');
    } catch {
      setError(t('mod.userFlairFailed'));
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(flair: UserFlair) {
    setError(null);
    try {
      await deleteUserFlair(slug, flair.id);
      setFlairs((arr) => arr.filter((f) => f.id !== flair.id));
      if (selected === String(flair.id)) setSelected('');
    } catch {
      setError(t('mod.userFlairFailed'));
    }
  }

  async function handleAllowSelf(value: boolean) {
    setError(null);
    try {
      await onAllowSelfChange?.(value);
    } catch {
      setError(t('mod.userFlairFailed'));
    }
  }

  return (
    <Card>
      <h2 className="text-base font-semibold tracking-tight">{t('mod.userFlairTitle')}</h2>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">{t('mod.userFlairHint')}</p>
      {onAllowSelfChange && (
        <label className="mt-3 flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={Boolean(allowSelf)}
            onChange={(e) => void handleAllowSelf(e.target.checked)}
          />
          {t('mod.userFlairAllowSelf')}
        </label>
      )}
      {canSelect && (
        <div className="mt-3 flex flex-col gap-1.5">
          <label
            htmlFor="my-user-flair"
            className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-muted)]"
          >
            {t('mod.userFlairMine')}
          </label>
          <select
            id="my-user-flair"
            value={selected}
            onChange={(e) => void handleSelect(e.target.value)}
            className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-2 text-sm text-[var(--color-text)]"
          >
            <option value="">{t('mod.userFlairNone')}</option>
            {flairs.map((f) => (
              <option key={f.id} value={f.id}>
                {f.text}
              </option>
            ))}
          </select>
        </div>
      )}
      {isModerator && (
        <>
          <ul className="mt-3 flex flex-wrap gap-2">
            {flairs.map((f) => (
              <li
                key={f.id}
                className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium"
                style={{ color: f.color, borderColor: `${f.color}44` }}
              >
                {f.text}
                <button
                  type="button"
                  aria-label={t('mod.userFlairDeleteLabel', { flair: f.text })}
                  onClick={() => void handleDelete(f)}
                  className="ml-1 text-[var(--color-text-muted)] hover:text-[var(--color-danger)]"
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
          <form onSubmit={handleCreate} className="mt-3 flex flex-wrap items-end gap-3">
            <Input
              name="user-flair-text"
              label={t('mod.userFlairText')}
              value={text}
              maxLength={40}
              onChange={(e) => setText(e.target.value)}
            />
            <input
              type="color"
              aria-label={t('mod.userFlairColor')}
              value={color}
              onChange={(e) => setColor(e.target.value)}
              className="h-10 w-10 rounded border border-[var(--color-border)] bg-transparent"
            />
            <Button type="submit" loading={busy} disabled={!text.trim()}>
              {t('mod.userFlairAdd')}
            </Button>
          </form>
        </>
      )}
      {error && (
        <p role="alert" className="mt-2 text-sm text-[var(--color-danger)]">
          {error}
        </p>
      )}
    </Card>
  );
}

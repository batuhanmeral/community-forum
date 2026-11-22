import { useEffect, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import type { AxiosError } from 'axios';
import {
  createFeed,
  deleteFeed,
  listMyFeeds,
  updateFeed,
  type CustomFeed,
  type CustomFeedInput,
} from '@/api/customFeeds';
import { listCommunities } from '@/api/communities';
import { useAppSelector } from '@/app/hooks';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { PageTitle } from '@/components/ui/PageTitle';

const EMPTY: CustomFeedInput = { name: '', description: '', is_public: false, communities: [] };

/** Manage the signed-in user's custom feeds: create, edit, delete. */
export function CustomFeedsPage() {
  const { t } = useTranslation();
  const username = useAppSelector((s) => s.auth.user?.username ?? '');
  const [feeds, setFeeds] = useState<CustomFeed[]>([]);
  const [loading, setLoading] = useState(true);
  const [joined, setJoined] = useState<string[]>([]);
  const [editing, setEditing] = useState<CustomFeed | null>(null);

  useEffect(() => {
    listMyFeeds()
      .then((d) => setFeeds(d.results))
      .catch(() => setFeeds([]))
      .finally(() => setLoading(false));
    listCommunities({ joined: true, ordering: 'name', page_size: 100 })
      .then((d) => setJoined(d.results.map((c) => c.slug)))
      .catch(() => undefined);
  }, []);

  async function handleDelete(feed: CustomFeed) {
    await deleteFeed(username, feed.slug);
    setFeeds((arr) => arr.filter((f) => f.id !== feed.id));
    if (editing?.id === feed.id) setEditing(null);
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4">
      <PageTitle title={t('customFeeds.title')} />
      <h1 className="text-2xl font-bold tracking-tight">{t('customFeeds.title')}</h1>
      <p className="text-sm text-[var(--color-text-muted)]">{t('customFeeds.hint')}</p>

      <FeedForm
        key={editing?.id ?? 'new'}
        initial={editing ?? undefined}
        suggestions={joined}
        onCancel={editing ? () => setEditing(null) : undefined}
        onSave={async (input) => {
          if (editing) {
            const saved = await updateFeed(username, editing.slug, input);
            setFeeds((arr) => arr.map((f) => (f.id === saved.id ? saved : f)));
            setEditing(null);
          } else {
            const created = await createFeed(input);
            setFeeds((arr) => [...arr, created]);
          }
        }}
      />

      {loading ? (
        <p className="text-sm text-[var(--color-text-muted)]">{t('common.loading')}</p>
      ) : feeds.length === 0 ? (
        <p className="text-sm text-[var(--color-text-dim)]">{t('customFeeds.empty')}</p>
      ) : (
        feeds.map((f) => (
          <Card key={f.id}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="min-w-0">
                <Link
                  to={`/u/${username}/feeds/${f.slug}`}
                  className="text-base font-semibold hover:underline"
                >
                  {f.name}
                </Link>
                <p className="text-xs text-[var(--color-text-muted)]">
                  {f.is_public ? t('customFeeds.public') : t('customFeeds.private')} ·{' '}
                  {t('customFeeds.communityCount', { count: f.communities.length })}
                </p>
              </div>
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" onClick={() => setEditing(f)}>
                  {t('common.edit')}
                </Button>
                <Button variant="ghost" size="sm" onClick={() => handleDelete(f)}>
                  {t('common.delete')}
                </Button>
              </div>
            </div>
          </Card>
        ))
      )}
    </div>
  );
}

interface FeedFormProps {
  initial?: CustomFeed;
  suggestions: string[];
  onSave: (input: CustomFeedInput) => Promise<void>;
  onCancel?: () => void;
}

function FeedForm({ initial, suggestions, onSave, onCancel }: FeedFormProps) {
  const { t } = useTranslation();
  const [form, setForm] = useState<CustomFeedInput>(
    initial
      ? {
          name: initial.name,
          description: initial.description,
          is_public: initial.is_public,
          communities: initial.communities,
        }
      : EMPTY,
  );
  const [slugInput, setSlugInput] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function addCommunity() {
    const slug = slugInput.trim().replace(/^c\//, '').toLowerCase();
    if (slug && !form.communities.includes(slug)) {
      setForm((f) => ({ ...f, communities: [...f.communities, slug] }));
    }
    setSlugInput('');
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await onSave(form);
      if (!initial) setForm(EMPTY);
    } catch (err) {
      const data = (err as AxiosError<Record<string, unknown>>).response?.data;
      const first = data && Object.values(data).flat()[0];
      setError(typeof first === 'string' ? first : t('customFeeds.saveFailed'));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <h2 className="text-base font-semibold">
          {initial ? t('customFeeds.editTitle') : t('customFeeds.createTitle')}
        </h2>
        <Input
          name="name"
          label={t('customFeeds.name')}
          value={form.name}
          maxLength={50}
          required
          onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
        />
        <Input
          name="description"
          label={t('customFeeds.description')}
          value={form.description}
          maxLength={280}
          onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
        />
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={form.is_public}
            onChange={(e) => setForm((f) => ({ ...f, is_public: e.target.checked }))}
            className="h-4 w-4 accent-[var(--color-link)]"
          />
          {t('customFeeds.makePublic')}
        </label>
        <div className="flex flex-col gap-2">
          <div className="flex items-end gap-2">
            <Input
              name="community"
              label={t('customFeeds.addCommunity')}
              list="feed-community-suggestions"
              value={slugInput}
              onChange={(e) => setSlugInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  addCommunity();
                }
              }}
            />
            <datalist id="feed-community-suggestions">
              {suggestions.map((s) => (
                <option key={s} value={s} />
              ))}
            </datalist>
            <Button type="button" variant="secondary" onClick={addCommunity}>
              {t('customFeeds.add')}
            </Button>
          </div>
          <ul className="flex flex-wrap gap-2">
            {form.communities.map((c) => (
              <li
                key={c}
                className="inline-flex items-center gap-1 rounded-full border border-[var(--color-border)] px-2.5 py-1 text-xs"
              >
                c/{c}
                <button
                  type="button"
                  aria-label={t('customFeeds.remove', { slug: c })}
                  onClick={() =>
                    setForm((f) => ({ ...f, communities: f.communities.filter((x) => x !== c) }))
                  }
                  className="text-[var(--color-text-muted)] hover:text-[var(--color-danger)]"
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        </div>
        {error && (
          <p role="alert" className="text-sm text-[var(--color-danger)]">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          {onCancel && (
            <Button type="button" variant="secondary" onClick={onCancel}>
              {t('common.cancel')}
            </Button>
          )}
          <Button type="submit" loading={saving}>
            {t('common.save')}
          </Button>
        </div>
      </form>
    </Card>
  );
}

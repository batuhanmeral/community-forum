import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { AxiosError } from 'axios';
import { createCommunity } from '@/api/communities';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';

type FieldErrors = Partial<Record<'slug' | 'name' | 'description' | 'avatar' | 'non_field', string>>;

export function CommunityCreatePage() {
  const navigate = useNavigate();
  const [slug, setSlug] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isNsfw, setIsNsfw] = useState(false);
  const [avatar, setAvatar] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setErrors({});
    setLoading(true);
    try {
      const created = await createCommunity({
        slug: slug.trim().toLowerCase(),
        name: name.trim(),
        description: description.trim(),
        is_nsfw: isNsfw,
        avatar,
      });
      navigate(`/c/${created.slug}`, { replace: true });
    } catch (err) {
      const ax = err as AxiosError<Record<string, string[] | string>>;
      const data = ax.response?.data ?? {};
      const fe: FieldErrors = {};
      for (const [key, val] of Object.entries(data)) {
        const msg = Array.isArray(val) ? val[0] : String(val);
        if (key === 'slug' || key === 'name' || key === 'description' || key === 'avatar')
          fe[key] = msg;
        else fe.non_field = msg;
      }
      setErrors(fe);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Create a community</h1>
        <p className="mt-1 text-sm text-[var(--color-text-muted)]">
          Pick a slug — it can't be changed later.
        </p>
      </div>

      <Card>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <Input
            name="slug"
            label="Slug (URL identifier)"
            placeholder="e.g. webdev"
            value={slug}
            onChange={(e) => setSlug(e.target.value.replace(/[^a-z0-9_-]/gi, '').toLowerCase())}
            error={errors.slug}
            required
            maxLength={32}
            pattern="[a-z0-9_-]{3,32}"
          />
          <Input
            name="name"
            label="Display name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            error={errors.name}
            required
            maxLength={64}
          />
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="description"
              className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-muted)]"
            >
              Description
            </label>
            <textarea
              id="description"
              name="description"
              rows={4}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={500}
              className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-2 text-sm text-[var(--color-text)] placeholder:text-[var(--color-text-dim)] focus:border-[var(--color-accent)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]/30"
            />
            {errors.description && (
              <p className="text-xs text-[var(--color-danger)]">{errors.description}</p>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-muted)]">
              Icon (optional)
            </label>
            <input
              type="file"
              accept="image/*"
              onChange={(e) => setAvatar(e.target.files?.[0] ?? null)}
              className="text-sm text-[var(--color-text-muted)] file:mr-3 file:rounded-full file:border-0 file:bg-[var(--color-surface-hover)] file:px-4 file:py-2 file:text-sm file:font-medium file:text-[var(--color-text)] hover:file:bg-[var(--color-border)]"
            />
            {errors.avatar && <p className="text-xs text-[var(--color-danger)]">{errors.avatar}</p>}
          </div>

          <label className="flex items-center gap-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-2.5">
            <input
              type="checkbox"
              checked={isNsfw}
              onChange={(e) => setIsNsfw(e.target.checked)}
              className="h-4 w-4 accent-[var(--color-accent)]"
            />
            <span className="text-sm">
              <span className="font-medium">NSFW</span>
              <span className="ml-2 text-[var(--color-text-muted)]">
                Mark this community as Not Safe For Work.
              </span>
            </span>
          </label>

          {errors.non_field && (
            <p className="text-sm text-[var(--color-danger)]">{errors.non_field}</p>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => navigate(-1)}>
              Cancel
            </Button>
            <Button type="submit" loading={loading}>
              Create community
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}

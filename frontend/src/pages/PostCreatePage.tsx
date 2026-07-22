import { useEffect, useState, type FormEvent } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { AxiosError } from 'axios';
import { createPost } from '@/api/posts';
import type { PostKind } from '@/features/posts/types';
import { getCommunity, listCommunities, listFlairs } from '@/api/communities';
import type { Community, Flair } from '@/features/communities/types';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { MarkdownEditor } from '@/components/posts/MarkdownEditor';
import { clearDraft, loadDraft, saveDraft } from '@/lib/draft';
import { timeAgo } from '@/lib/time';
import { cn } from '@/lib/cn';

const KIND_TABS: Array<{ value: PostKind; label: string; icon: React.ReactNode }> = [
  {
    value: 'text',
    label: 'Text',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4">
        <path d="M4 6h16M4 12h16M4 18h10" />
      </svg>
    ),
  },
  {
    value: 'image',
    label: 'Image',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4">
        <rect x="3" y="4" width="18" height="16" rx="2" />
        <circle cx="9" cy="10" r="2" />
        <path d="m3 18 6-5 5 4 4-3 3 3" />
      </svg>
    ),
  },
  {
    value: 'link',
    label: 'Link',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4">
        <path d="M10 14a4 4 0 0 0 5.66 0l3-3a4 4 0 0 0-5.66-5.66L11 7" />
        <path d="M14 10a4 4 0 0 0-5.66 0l-3 3a4 4 0 0 0 5.66 5.66L13 17" />
      </svg>
    ),
  },
  {
    value: 'poll',
    label: 'Poll',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4">
        <path d="M4 20V8M10 20V4M16 20v-8M22 20H2" />
      </svg>
    ),
  },
];

type FieldErrors = Partial<
  Record<'title' | 'body' | 'url' | 'image' | 'poll_input' | 'non_field' | 'community', string>
>;

export function PostCreatePage() {
  const params = useParams<{ slug?: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const kindParam = searchParams.get('kind');
  const isValidKind = (k: string | null): k is PostKind =>
    k === 'text' || k === 'link' || k === 'image' || k === 'poll';

  // A pending draft seeds the form unless the URL explicitly picks community/kind.
  const [draft] = useState(loadDraft);

  const [communities, setCommunities] = useState<Community[]>([]);
  const [communitySlug, setCommunitySlug] = useState(
    params.slug ?? searchParams.get('c') ?? draft?.community ?? '',
  );
  const [kind, setKind] = useState<PostKind>(
    isValidKind(kindParam) ? kindParam : isValidKind(draft?.kind ?? null) ? (draft!.kind as PostKind) : 'text',
  );
  const [flairs, setFlairs] = useState<Flair[]>([]);
  const [flairId, setFlairId] = useState<number | ''>('');
  const [title, setTitle] = useState(draft?.title ?? '');
  const [body, setBody] = useState(draft?.body ?? '');
  const [url, setUrl] = useState(draft?.url ?? '');
  const [draftNotice, setDraftNotice] = useState<string | null>(
    draft ? `Draft restored (saved ${timeAgo(draft.savedAt)})` : null,
  );
  const [image, setImage] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [isNsfw, setIsNsfw] = useState(false);
  const [pollOptions, setPollOptions] = useState<string[]>(['', '']);
  const [pollClosesAt, setPollClosesAt] = useState(defaultPollClose());
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});

  useEffect(() => {
    if (params.slug) {
      getCommunity(params.slug)
        .then((c) => setCommunities([c]))
        .catch(() => undefined);
    } else {
      listCommunities({ ordering: '-member_count' })
        .then((d) => setCommunities(d.results))
        .catch(() => undefined);
    }
  }, [params.slug]);

  // Autosave the draft (debounced) while the user types.
  useEffect(() => {
    const t = setTimeout(() => {
      saveDraft({ community: communitySlug, kind, title, body, url });
    }, 600);
    return () => clearTimeout(t);
  }, [communitySlug, kind, title, body, url]);

  function discardDraft() {
    clearDraft();
    setTitle('');
    setBody('');
    setUrl('');
    setDraftNotice(null);
  }

  useEffect(() => {
    setFlairId('');
    if (!communitySlug) {
      setFlairs([]);
      return;
    }
    listFlairs(communitySlug)
      .then(setFlairs)
      .catch(() => setFlairs([]));
  }, [communitySlug]);

  useEffect(() => {
    if (!image) {
      setImagePreview(null);
      return;
    }
    const url = URL.createObjectURL(image);
    setImagePreview(url);
    return () => URL.revokeObjectURL(url);
  }, [image]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setErrors({});
    if (!communitySlug) {
      setErrors({ community: 'Please pick a community.' });
      return;
    }
    setLoading(true);
    try {
      const post = await createPost(communitySlug, {
        kind,
        title: title.trim(),
        body: kind === 'text' ? body : undefined,
        url: kind === 'link' ? url.trim() : undefined,
        image: kind === 'image' ? image : null,
        is_nsfw: isNsfw,
        flair: flairId === '' ? null : flairId,
        poll_options: kind === 'poll' ? pollOptions : undefined,
        poll_closes_at: kind === 'poll' ? new Date(pollClosesAt).toISOString() : undefined,
      });
      clearDraft();
      navigate(`/posts/${post.id}`, { replace: true });
    } catch (err) {
      const ax = err as AxiosError<Record<string, string[] | string>>;
      const data = ax.response?.data ?? {};
      const fe: FieldErrors = {};
      for (const [key, val] of Object.entries(data)) {
        const msg = Array.isArray(val) ? val[0] : String(val);
        if (key === 'title' || key === 'body' || key === 'url' || key === 'image')
          fe[key] = msg;
        else if (key === 'poll_input') fe.poll_input = msg;
        else fe.non_field = msg;
      }
      setErrors(fe);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5">
      <h1 className="text-2xl font-bold tracking-tight">Create a post</h1>

      <Card>
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-muted)]">
            Community
          </label>
          {params.slug ? (
            <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-2.5 text-sm">
              c/{params.slug}
            </div>
          ) : (
            <select
              value={communitySlug}
              onChange={(e) => setCommunitySlug(e.target.value)}
              className="h-11 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 text-sm focus:border-[var(--color-accent)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]/30"
            >
              <option value="" disabled>
                Choose a community
              </option>
              {communities.map((c) => (
                <option key={c.id} value={c.slug}>
                  c/{c.slug}
                </option>
              ))}
            </select>
          )}
          {errors.community && (
            <p className="text-xs text-[var(--color-danger)]">{errors.community}</p>
          )}
        </div>
      </Card>

      <Card padded={false}>
        <div className="flex border-b border-[var(--color-border)]">
          {KIND_TABS.map((tab) => (
            <button
              key={tab.value}
              type="button"
              onClick={() => setKind(tab.value)}
              className={cn(
                'flex flex-1 items-center justify-center gap-2 px-4 py-3 text-sm font-medium transition-colors',
                kind === tab.value
                  ? 'border-b-2 border-[var(--color-accent)] text-[var(--color-text)]'
                  : 'border-b-2 border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text)]',
              )}
            >
              {tab.icon}
              <span>{tab.label}</span>
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4 p-5">
          {draftNotice && (
            <div className="flex items-center justify-between gap-3 rounded-xl border border-[rgba(97,218,251,0.25)] bg-[var(--color-accent-dim)] px-3 py-2 text-[13px] text-[var(--color-accent)]">
              <span>{draftNotice}</span>
              <button
                type="button"
                onClick={discardDraft}
                className="font-medium underline-offset-2 hover:underline"
              >
                Discard draft
              </button>
            </div>
          )}
          <Input
            name="title"
            label="Title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            error={errors.title}
            required
            maxLength={300}
          />

          {kind === 'text' && (
            <MarkdownEditor value={body} onChange={setBody} error={errors.body} />
          )}

          {kind === 'link' && (
            <Input
              name="url"
              type="url"
              label="URL"
              placeholder="https://..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              error={errors.url}
              required
            />
          )}

          {kind === 'image' && (
            <div className="flex flex-col gap-2">
              <label className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-muted)]">
                Image
              </label>
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={(e) => setImage(e.target.files?.[0] ?? null)}
                className="text-sm text-[var(--color-text-muted)] file:mr-3 file:rounded-full file:border-0 file:bg-[var(--color-surface-hover)] file:px-4 file:py-2 file:text-sm file:font-medium file:text-[var(--color-text)] hover:file:bg-[var(--color-border)]"
              />
              {imagePreview && (
                <div className="overflow-hidden rounded-lg border border-[var(--color-border)]">
                  <img src={imagePreview} alt="" className="max-h-80 w-full object-contain" />
                </div>
              )}
              {errors.image && <p className="text-xs text-[var(--color-danger)]">{errors.image}</p>}
              <p className="text-xs text-[var(--color-text-dim)]">JPEG, PNG or WEBP. Max 5 MB.</p>
            </div>
          )}

          {kind === 'poll' && (
            <div className="flex flex-col gap-3">
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-muted)]">
                  Options
                </label>
                {pollOptions.map((opt, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <input
                      type="text"
                      value={opt}
                      onChange={(e) => {
                        const next = [...pollOptions];
                        next[i] = e.target.value;
                        setPollOptions(next);
                      }}
                      placeholder={`Option ${i + 1}`}
                      className="h-10 flex-1 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 text-sm focus:border-[var(--color-accent)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]/30"
                      maxLength={120}
                    />
                    {pollOptions.length > 2 && (
                      <button
                        type="button"
                        onClick={() => setPollOptions(pollOptions.filter((_, j) => j !== i))}
                        className="rounded-full p-2 text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-danger)]"
                        aria-label="Remove option"
                      >
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4">
                          <path d="M6 6l12 12M6 18 18 6" />
                        </svg>
                      </button>
                    )}
                  </div>
                ))}
                {pollOptions.length < 8 && (
                  <button
                    type="button"
                    onClick={() => setPollOptions([...pollOptions, ''])}
                    className="self-start text-sm text-[var(--color-accent)] hover:underline"
                  >
                    + Add option
                  </button>
                )}
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-muted)]">
                  Closes at
                </label>
                <input
                  type="datetime-local"
                  value={pollClosesAt}
                  onChange={(e) => setPollClosesAt(e.target.value)}
                  className="h-11 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 text-sm focus:border-[var(--color-accent)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]/30"
                />
              </div>
              {errors.poll_input && (
                <p className="text-xs text-[var(--color-danger)]">{errors.poll_input}</p>
              )}
            </div>
          )}

          {flairs.length > 0 && (
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-muted)]">
                Flair (optional)
              </label>
              <div className="flex flex-wrap items-center gap-1.5">
                {flairs.map((f) => (
                  <button
                    key={f.id}
                    type="button"
                    onClick={() => setFlairId(flairId === f.id ? '' : f.id)}
                    className={cn(
                      'inline-flex items-center rounded-full border px-3 py-1 text-[12px] font-medium transition',
                      flairId === f.id ? 'ring-2 ring-[var(--color-accent)]/40' : 'opacity-75 hover:opacity-100',
                    )}
                    style={{
                      color: f.color,
                      borderColor: `${f.color}44`,
                      background: `${f.color}14`,
                    }}
                  >
                    {f.name}
                  </button>
                ))}
              </div>
            </div>
          )}

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
                Mark this post as Not Safe For Work.
              </span>
            </span>
          </label>

          {errors.non_field && (
            <p className="text-sm text-[var(--color-danger)]">{errors.non_field}</p>
          )}

          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="secondary" onClick={() => navigate(-1)}>
              Cancel
            </Button>
            <Button type="submit" loading={loading}>
              Post
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}

function defaultPollClose(): string {
  const d = new Date();
  d.setDate(d.getDate() + 3);
  d.setSeconds(0, 0);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

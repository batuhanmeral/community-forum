import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import type { AxiosError } from 'axios';
import { crosspostPost } from '@/api/posts';
import { listCommunities } from '@/api/communities';
import type { Community } from '@/features/communities/types';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { Repeat2 } from 'lucide-react';

interface CrosspostButtonProps {
  postId: number;
  title: string;
}

/** Shares a post into another community the viewer has joined. */
export function CrosspostButton({ postId, title }: CrosspostButtonProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [communities, setCommunities] = useState<Community[]>([]);
  const [slug, setSlug] = useState('');
  const [newTitle, setNewTitle] = useState(title);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function show() {
    setOpen(true);
    setError(null);
    listCommunities({ joined: true, ordering: 'name', page_size: 100 })
      .then((d) => setCommunities(d.results))
      .catch(() => setError(t('crosspost.loadFailed')));
  }

  async function submit() {
    if (!slug) {
      setError(t('crosspost.pick'));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await crosspostPost(postId, slug, newTitle.trim() || undefined);
      setOpen(false);
      navigate(`/posts/${created.id}`);
    } catch (err) {
      setError(t(crosspostErrorKey(err)));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Button variant="ghost" size="sm" onClick={show}>
        <Repeat2 className="h-[15px] w-[15px]" />
        {t('crosspost.action')}
      </Button>
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={t('crosspost.title')}
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button onClick={submit} loading={busy}>
              {t('crosspost.submit')}
            </Button>
          </>
        }
      >
        <label className="flex flex-col gap-1 text-sm">
          {t('postForm.community')}
          <select
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            className="h-10 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3"
          >
            <option value="" disabled>
              {t('postForm.chooseCommunity')}
            </option>
            {communities.map((c) => (
              <option key={c.slug} value={c.slug}>
                c/{c.slug}
              </option>
            ))}
          </select>
        </label>
        <label className="mt-3 flex flex-col gap-1 text-sm">
          {t('postForm.title')}
          <input
            value={newTitle}
            maxLength={300}
            onChange={(e) => setNewTitle(e.target.value)}
            className="h-10 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3"
          />
        </label>
        {error && (
          <p role="alert" className="mt-2 text-sm text-[var(--color-danger)]">
            {error}
          </p>
        )}
      </Modal>
    </>
  );
}

// Server messages are English; show our own translated text and fall back to a generic one.
const KNOWN_ERRORS: [RegExp, string][] = [
  [/already crossposted/i, 'crosspost.duplicate'],
  [/already in this community/i, 'crosspost.sameCommunity'],
  [/polls cannot be crossposted/i, 'crosspost.polls'],
];

function crosspostErrorKey(err: unknown): string {
  const response = (err as AxiosError).response;
  if (response?.status === 403) return 'crosspost.forbidden';
  const text = JSON.stringify(response?.data ?? '');
  return KNOWN_ERRORS.find(([pattern]) => pattern.test(text))?.[1] ?? 'crosspost.failed';
}

import { useState } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { approvePost, rejectPost } from '@/api/posts';
import type { Post } from '@/features/posts/types';
import { Button } from '@/components/ui/Button';

/** Approve/reject for the version on screen; `onSettled` refetches so the page shows the server's state. */
export function PendingPostActions({ post, onSettled }: { post: Post; onSettled: () => void }) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function act(kind: 'approve' | 'reject') {
    setBusy(true);
    setError(null);
    try {
      if (kind === 'approve') await approvePost(post.id, post.edited_at);
      else await rejectPost(post.id);
      onSettled();
    } catch (err) {
      const stale = axios.isAxiosError(err) && err.response?.status === 409;
      setError(t(stale ? 'mod.approvalStale' : 'mod.actionFailed'));
      if (stale) onSettled();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-2">
      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" size="sm" loading={busy} onClick={() => act('reject')}>
          {t('mod.reject')}
        </Button>
        <Button size="sm" loading={busy} onClick={() => act('approve')}>
          {t('mod.approve')}
        </Button>
      </div>
      {error && <p className="mt-2 text-sm text-[var(--color-danger)]">{error}</p>}
    </div>
  );
}

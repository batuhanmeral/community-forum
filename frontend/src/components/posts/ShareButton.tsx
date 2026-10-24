import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, Share } from 'lucide-react';

const SHARE_STATUS_RESET_MS = 2000;

type ShareStatus = 'idle' | 'copied' | 'failed';

const SHARE_LABEL_KEYS: Record<ShareStatus, string> = {
  idle: 'post.share',
  copied: 'post.shareCopied',
  failed: 'post.shareFailed',
};

export function ShareButton({ postId, title }: { postId: number; title: string }) {
  const { t } = useTranslation();
  const [status, setStatus] = useState<ShareStatus>('idle');

  useEffect(() => {
    if (status === 'idle') return;
    const timer = setTimeout(() => setStatus('idle'), SHARE_STATUS_RESET_MS);
    return () => clearTimeout(timer);
  }, [status]);

  async function share() {
    const url = `${window.location.origin}/posts/${postId}`;
    if (navigator.share) {
      try {
        await navigator.share({ title, url });
        return;
      } catch (e) {
        // Dismissing the share sheet is not a failure; anything else falls back to copying.
        if (e instanceof DOMException && e.name === 'AbortError') return;
      }
    }
    try {
      await navigator.clipboard.writeText(url);
      setStatus('copied');
    } catch {
      setStatus('failed');
    }
  }

  const label = t(SHARE_LABEL_KEYS[status]);
  const Icon = status === 'copied' ? Check : Share;
  return (
    <button
      type="button"
      className="inline-flex items-center gap-1.5 rounded-[var(--radius-control)] bg-[var(--color-bg-elevated)] px-3 py-1.5 text-[12.5px] font-medium text-[var(--color-text-muted)] transition hover:bg-[var(--color-bg-3)] hover:text-[var(--color-text)]"
      onClick={share}
      aria-label={label}
    >
      <Icon className="h-[15px] w-[15px]" />
      <span aria-live="polite" className="max-[480px]:hidden">{label}</span>
    </button>
  );
}

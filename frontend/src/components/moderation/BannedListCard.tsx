import { useCallback, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { listBans, unbanUser, type BannedMember } from '@/api/moderation';
import { Avatar } from '@/components/ui/Avatar';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { usePagedList } from '@/lib/usePagedList';
import { timeAgo } from '@/lib/time';

export function BannedListCard({ slug }: { slug: string }) {
  const { t } = useTranslation();
  const fetchPage = useCallback((page: number) => listBans(slug, page), [slug]);
  const { items, loading, loadFailed, nextPage, loadMore, loadMoreFailed, remove } = usePagedList(fetchPage);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleUnban(member: BannedMember) {
    setBusyId(member.id);
    setError(null);
    try {
      await unbanUser(slug, member.username);
      remove(member.id);
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail ?? t('mod.unbanFailed'));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Card>
      <h2 className="text-base font-semibold tracking-tight">{t('mod.bansTitle')}</h2>
      {error && <p className="mt-2 text-sm text-[var(--color-danger)]">{error}</p>}
      <div className="mt-3 flex flex-col gap-2">
        {loading ? (
          <p className="text-sm text-[var(--color-text-muted)]">{t('mod.loading')}</p>
        ) : loadFailed ? (
          <p className="text-sm text-[var(--color-danger)]">{t('mod.loadFailed')}</p>
        ) : items.length === 0 ? (
          <p className="text-sm text-[var(--color-text-muted)]">{t('mod.bansEmpty')}</p>
        ) : (
          items.map((m) => (
            <div
              key={m.id}
              className="flex flex-wrap items-center gap-3 rounded-[12px] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-4 py-3"
            >
              <Avatar src={m.avatar} alt={m.username} size="sm" />
              <div className="min-w-0 flex-1">
                <Link to={`/u/${m.username}`} className="text-sm font-medium hover:underline">
                  u/{m.username}
                </Link>
                <div className="text-xs text-[var(--color-text-muted)]">
                  {m.banned_by_username && t('mod.bannedBy', { username: m.banned_by_username })}
                  {m.banned_at && ` · ${timeAgo(m.banned_at)}`}
                </div>
              </div>
              <Button
                variant="secondary"
                size="sm"
                loading={busyId === m.id}
                onClick={() => handleUnban(m)}
              >
                {t('mod.unban')}
              </Button>
            </div>
          ))
        )}
      </div>
      {nextPage !== null && (
        <button
          type="button"
          onClick={loadMore}
          className="mt-3 text-sm text-[var(--color-accent)] hover:underline"
        >
          {t('mod.loadMore')}
        </button>
      )}
      {loadMoreFailed && (
        <p className="mt-2 text-sm text-[var(--color-danger)]">{t('mod.loadMoreFailed')}</p>
      )}
    </Card>
  );
}

import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  getModmailThread,
  listModmailMessages,
  markModmailRead,
  sendModmailMessage,
  updateModmailThread,
  type ModmailMessage,
  type ModmailThread,
} from '@/api/modmail';
import { useAppSelector } from '@/app/hooks';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { PageTitle } from '@/components/ui/PageTitle';
import { useRealtime } from '@/features/realtime/realtime';
import type { RealtimeEvent } from '@/lib/realtime';
import { timeAgo } from '@/lib/time';
import { cn } from '@/lib/cn';

const isModmailEvent = (e: RealtimeEvent) => e.type === 'modmail.updated' || e.type === 'resync';

export function ModmailThreadPage() {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const threadId = Number(id);
  const userId = useAppSelector((s) => s.auth.user?.id);
  const [thread, setThread] = useState<ModmailThread | null>(null);
  const [messages, setMessages] = useState<ModmailMessage[]>([]);
  const [notFound, setNotFound] = useState(false);
  const [body, setBody] = useState('');
  const [internal, setInternal] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);

  const load = useCallback(async () => {
    try {
      const [th, page] = await Promise.all([
        getModmailThread(threadId),
        listModmailMessages(threadId),
      ]);
      setThread(th);
      setMessages(page.results);
      void markModmailRead(threadId).catch(() => undefined);
    } catch {
      setNotFound(true);
    }
  }, [threadId]);

  useEffect(() => {
    void load();
  }, [load]);
  useRealtime(isModmailEvent, () => void load());

  // `assigned_to` is only sent to moderators, so its presence marks the moderator view.
  const isModerator = thread !== null && 'assigned_to' in thread;

  async function send(e: FormEvent) {
    e.preventDefault();
    if (busy || !body.trim()) return;
    setBusy(true);
    setError(false);
    try {
      const sent = await sendModmailMessage(threadId, body.trim(), isModerator && internal);
      setMessages((m) => [...m, sent]);
      setBody('');
      setInternal(false);
      if (thread?.status === 'archived' && !isModerator) setThread({ ...thread, status: 'open' });
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  }

  async function patch(values: { status?: 'open' | 'archived'; assigned_to?: number | null }) {
    setError(false);
    try {
      setThread(await updateModmailThread(threadId, values));
    } catch {
      setError(true);
    }
  }

  if (notFound) return <p className="text-sm text-[var(--color-text-muted)]">{t('modmail.notFound')}</p>;
  if (!thread) return <p className="text-sm text-[var(--color-text-muted)]">{t('common.loading')}</p>;

  return (
    <div className="flex flex-col gap-4">
      <PageTitle title={thread.subject} />
      <div>
        <Link
          to={isModerator ? `/c/${thread.community}/modmail` : '/modmail'}
          className="text-xs text-[var(--color-link)] hover:underline"
        >
          {t('modmail.back')}
        </Link>
        <h1 className="mt-1 text-[22px] font-semibold tracking-tight">{thread.subject}</h1>
        <p className="text-xs text-[var(--color-text-muted)]">
          c/{thread.community}
          {isModerator && ` · u/${thread.creator_username ?? t('common.deleted')}`}
          {thread.status === 'archived' && ` · ${t('modmail.status_archived')}`}
        </p>
      </div>
      {isModerator && (
        <div className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => void patch({ status: thread.status === 'open' ? 'archived' : 'open' })}
          >
            {thread.status === 'open' ? t('modmail.archive') : t('modmail.reopen')}
          </Button>
          {thread.assigned_to === userId ? (
            <Button variant="secondary" size="sm" onClick={() => void patch({ assigned_to: null })}>
              {t('modmail.unassign')}
            </Button>
          ) : (
            userId !== undefined && (
              <Button variant="secondary" size="sm" onClick={() => void patch({ assigned_to: userId })}>
                {t('modmail.assignToMe')}
              </Button>
            )
          )}
          {thread.assigned_to_username && thread.assigned_to !== userId && (
            <span className="self-center text-xs text-[var(--color-text-muted)]">
              {t('modmail.assignedTo', { name: thread.assigned_to_username })}
            </span>
          )}
        </div>
      )}
      <ul className="flex flex-col gap-3">
        {messages.map((m) => (
          <li key={m.id}>
            <Card
              className={cn(m.is_internal && 'border-dashed')}
            >
              <p className="text-xs text-[var(--color-text-muted)]">
                {m.author_username
                  ? `u/${m.author_username}`
                  : m.from_moderator
                    ? t('modmail.modTeam')
                    : t('common.deleted')}
                {m.is_internal && ` · ${t('modmail.internalNote')}`}
                {' · '}
                {timeAgo(m.created)}
              </p>
              <p className="mt-1 whitespace-pre-wrap text-sm">{m.body}</p>
            </Card>
          </li>
        ))}
      </ul>
      <form onSubmit={send} className="flex flex-col gap-2">
        <label htmlFor="modmail-reply" className="sr-only">
          {t('modmail.reply')}
        </label>
        <textarea
          id="modmail-reply"
          rows={4}
          maxLength={5000}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder={t('modmail.reply')}
          className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-2 text-sm text-[var(--color-text)]"
        />
        <div className="flex items-center gap-3">
          <Button type="submit" loading={busy} disabled={!body.trim()}>
            {t('modmail.send')}
          </Button>
          {isModerator && (
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={internal} onChange={(e) => setInternal(e.target.checked)} />
              {t('modmail.internalNote')}
            </label>
          )}
        </div>
        {error && (
          <p role="alert" className="text-sm text-[var(--color-danger)]">
            {t('modmail.sendFailed')}
          </p>
        )}
      </form>
    </div>
  );
}

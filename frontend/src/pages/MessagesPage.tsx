import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { AxiosError } from 'axios';
import {
  listConversations,
  listMessages,
  markConversationRead,
  sendMessage,
  startConversation,
} from '@/api/messaging';
import type { Conversation, Message } from '@/features/messaging/types';
import { useAppDispatch, useAppSelector } from '@/app/hooks';
import { setDMUnreadCount } from '@/features/messaging/messagingSlice';
import { Avatar } from '@/components/ui/Avatar';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { timeAgo } from '@/lib/time';
import { cn } from '@/lib/cn';

export function MessagesPage() {
  const { id } = useParams<{ id?: string }>();
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const currentUserId = useAppSelector((s) => s.auth.user?.id);

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [convsLoading, setConvsLoading] = useState(true);
  const [newOpen, setNewOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    listConversations()
      .then((d) => {
        if (cancelled) return;
        setConversations(d);
        dispatch(setDMUnreadCount(d.reduce((acc, c) => acc + c.unread_count, 0)));
      })
      .catch(() => undefined)
      .finally(() => {
        if (!cancelled) setConvsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [dispatch]);

  const selected = useMemo(
    () => conversations.find((c) => c.id === Number(id)) ?? null,
    [conversations, id],
  );

  function handleConvChange(updater: (prev: Conversation[]) => Conversation[]) {
    setConversations((prev) => {
      const next = updater(prev);
      dispatch(setDMUnreadCount(next.reduce((acc, c) => acc + c.unread_count, 0)));
      return next;
    });
  }

  async function handleNew(username: string): Promise<string | null> {
    try {
      const conv = await startConversation(username);
      // Avoid duplicate if already in list
      handleConvChange((prev) => (prev.some((c) => c.id === conv.id) ? prev : [conv, ...prev]));
      setNewOpen(false);
      navigate(`/messages/${conv.id}`);
      return null;
    } catch (err) {
      const ax = err as AxiosError<{ username?: string[]; detail?: string }>;
      return ax.response?.data?.username?.[0] ?? ax.response?.data?.detail ?? 'Could not start conversation.';
    }
  }

  return (
    <div className="grid h-[calc(100vh-128px)] grid-cols-[280px_minmax(0,1fr)] overflow-hidden rounded-[14px] border border-[var(--color-border)] bg-[var(--color-bg-1)] max-[720px]:grid-cols-1">
      {/* Inbox */}
      <aside className="flex flex-col border-r border-[var(--color-border)] max-[720px]:hidden">
        <div className="flex items-center justify-between gap-2 border-b border-[var(--color-border)] px-4 py-3.5">
          <h2 className="text-[15px] font-semibold tracking-tight">Inbox</h2>
          <button
            type="button"
            onClick={() => setNewOpen(true)}
            className="inline-flex items-center gap-1 rounded-full bg-[var(--color-accent)] px-3 py-1 text-[12px] font-semibold text-[#061218] transition hover:opacity-90"
          >
            + New
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {convsLoading ? (
            <p className="px-4 py-4 text-[13px] text-[var(--color-text-muted)]">Loading…</p>
          ) : conversations.length === 0 ? (
            <p className="px-4 py-4 text-[13px] text-[var(--color-text-muted)]">
              No conversations yet.
            </p>
          ) : (
            conversations.map((c) => (
              <ConversationRow
                key={c.id}
                conversation={c}
                active={c.id === selected?.id}
                currentUserId={currentUserId}
              />
            ))
          )}
        </div>
      </aside>

      {/* Chat */}
      <section className="flex min-w-0 flex-col">
        {selected ? (
          <ChatPane
            conversation={selected}
            currentUserId={currentUserId}
            onMessageSent={(msg) => {
              handleConvChange((prev) =>
                prev.map((c) => (c.id === selected.id ? { ...c, last_message: msg } : c)),
              );
            }}
            onRead={() => {
              handleConvChange((prev) =>
                prev.map((c) => (c.id === selected.id ? { ...c, unread_count: 0 } : c)),
              );
            }}
          />
        ) : (
          <div className="grid flex-1 place-items-center px-6 text-center">
            <div>
              <p className="text-sm text-[var(--color-text-muted)]">
                Select a conversation to start chatting.
              </p>
              <button
                type="button"
                onClick={() => setNewOpen(true)}
                className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-[var(--color-accent)] px-4 py-2 text-[13px] font-semibold text-[#061218]"
              >
                + Start a new conversation
              </button>
            </div>
          </div>
        )}
      </section>

      <NewConversationModal open={newOpen} onClose={() => setNewOpen(false)} onSubmit={handleNew} />
    </div>
  );
}

interface ConversationRowProps {
  conversation: Conversation;
  active: boolean;
  currentUserId?: number;
}

function ConversationRow({ conversation, active, currentUserId }: ConversationRowProps) {
  const other = conversation.other;
  const last = conversation.last_message;
  const isOwn = last?.sender === currentUserId;
  const preview = last ? (isOwn ? `You: ${last.body}` : last.body) : 'No messages yet.';

  return (
    <Link
      to={`/messages/${conversation.id}`}
      className={cn(
        'flex gap-3 border-b border-[var(--color-border)] px-4 py-3 transition',
        active ? 'bg-[var(--color-bg-elevated)]' : 'hover:bg-[var(--color-surface)]',
      )}
    >
      <Avatar alt={other?.username} size="md" />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-2">
          <span className="truncate text-[14px] font-medium">u/{other?.username ?? '?'}</span>
          {last && (
            <span className="font-mono shrink-0 text-[10.5px] text-[var(--color-text-dim)]">
              {timeAgo(last.created_at)}
            </span>
          )}
        </div>
        <div className="flex items-center justify-between gap-2">
          <p className="truncate text-[12.5px] text-[var(--color-text-muted)]">{preview}</p>
          {conversation.unread_count > 0 && (
            <span className="font-mono shrink-0 rounded-full bg-[var(--color-accent)] px-1.5 py-0.5 text-[10px] font-bold text-[#061218]">
              {conversation.unread_count}
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}

interface ChatPaneProps {
  conversation: Conversation;
  currentUserId?: number;
  onMessageSent: (msg: Message) => void;
  onRead: () => void;
}

function ChatPane({ conversation, currentUserId, onMessageSent, onRead }: ChatPaneProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [body, setBody] = useState('');
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listMessages(conversation.id)
      .then((d) => {
        if (!cancelled) setMessages(d.results);
      })
      .catch(() => undefined)
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    // Mark as read on open
    markConversationRead(conversation.id)
      .then(() => onRead())
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversation.id]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = body.trim();
    if (!trimmed || sending) return;
    setSending(true);
    try {
      const created = await sendMessage(conversation.id, trimmed);
      setMessages((m) => [...m, created]);
      onMessageSent(created);
      setBody('');
    } finally {
      setSending(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void handleSubmit(e as unknown as FormEvent);
    }
  }

  const other = conversation.other;

  return (
    <>
      <header className="flex items-center gap-3 border-b border-[var(--color-border)] px-5 py-3.5">
        <Avatar alt={other?.username} size="md" />
        <div className="min-w-0 flex-1">
          <Link
            to={`/u/${other?.username}`}
            className="text-[14px] font-semibold hover:text-[var(--color-accent)]"
          >
            u/{other?.username}
          </Link>
        </div>
      </header>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-5 py-4">
        {loading ? (
          <p className="text-sm text-[var(--color-text-muted)]">Loading messages…</p>
        ) : messages.length === 0 ? (
          <p className="text-center text-sm text-[var(--color-text-muted)]">
            No messages yet. Say hi.
          </p>
        ) : (
          <div className="flex flex-col gap-2.5">
            {messages.map((m, i) => {
              const own = m.sender === currentUserId;
              const showAvatar = !own && (i === 0 || messages[i - 1].sender !== m.sender);
              return (
                <div key={m.id} className={cn('flex items-end gap-2', own ? 'justify-end' : 'justify-start')}>
                  {!own && (
                    <div className={cn('w-7 shrink-0', !showAvatar && 'opacity-0')}>
                      <Avatar alt={m.sender_username} size="xs" />
                    </div>
                  )}
                  <div
                    className={cn(
                      'max-w-[70%] rounded-2xl px-3.5 py-2 text-[14px] leading-snug whitespace-pre-wrap',
                      own
                        ? 'bg-[var(--color-accent)] text-[#061218] rounded-br-md'
                        : 'bg-[var(--color-bg-elevated)] text-[var(--color-text)] rounded-bl-md',
                    )}
                  >
                    {m.body}
                    <div
                      className={cn(
                        'font-mono mt-1 flex items-center gap-1 text-[10px]',
                        own ? 'justify-end text-[#061218]/60' : 'text-[var(--color-text-dim)]',
                      )}
                    >
                      {timeAgo(m.created_at)}
                      {own && (
                        <span title={m.read_at ? 'Read' : 'Sent'}>
                          {m.read_at ? '✓✓' : '✓'}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <form
        onSubmit={handleSubmit}
        className="flex items-end gap-2 border-t border-[var(--color-border)] px-4 py-3"
      >
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          placeholder={`Message u/${other?.username}…`}
          className="max-h-32 flex-1 resize-none rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3.5 py-2 text-[14px] placeholder:text-[var(--color-text-dim)] focus:border-[var(--color-accent)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]/30"
        />
        <Button type="submit" size="md" loading={sending} disabled={!body.trim()}>
          Send
        </Button>
      </form>
    </>
  );
}

interface NewConvModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (username: string) => Promise<string | null>;
}

function NewConversationModal({ open, onClose, onSubmit }: NewConvModalProps) {
  const [username, setUsername] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setUsername('');
      setError(null);
    }
  }, [open]);

  async function handle(e: FormEvent) {
    e.preventDefault();
    const u = username.trim();
    if (!u || busy) return;
    setBusy(true);
    const err = await onSubmit(u);
    if (err) setError(err);
    setBusy(false);
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="New conversation"
      footer={
        <>
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="button" loading={busy} disabled={!username.trim()} onClick={handle}>
            Start
          </Button>
        </>
      }
    >
      <form onSubmit={handle} className="flex flex-col gap-3">
        <Input
          name="username"
          label="Username"
          placeholder="someone"
          value={username}
          onChange={(e) => setUsername(e.target.value.replace(/^@/, ''))}
          error={error}
          autoFocus
        />
      </form>
    </Modal>
  );
}

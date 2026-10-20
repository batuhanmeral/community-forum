import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { searchUsers, type UserSearchResult } from '@/api/search';
import { Avatar } from '@/components/ui/Avatar';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/cn';

interface CommentFormProps {
  initialValue?: string;
  placeholder?: string;
  autoFocus?: boolean;
  onSubmit: (body: string) => Promise<void>;
  onCancel?: () => void;
  submitLabel?: string;
}

interface MentionState {
  active: boolean;
  query: string;
  start: number;
  end: number;
  results: UserSearchResult[];
  selectedIndex: number;
}

const emptyMention: MentionState = {
  active: false,
  query: '',
  start: 0,
  end: 0,
  results: [],
  selectedIndex: 0,
};

export function CommentForm({
  initialValue = '',
  placeholder = 'Write a comment...',
  autoFocus,
  onSubmit,
  onCancel,
  submitLabel = 'Comment',
}: CommentFormProps) {
  const { t } = useTranslation();
  const [body, setBody] = useState(initialValue);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [mention, setMention] = useState<MentionState>(emptyMention);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const debounceRef = useRef<number | null>(null);
  const blurTimerRef = useRef<number | null>(null);

  // A pending blur timeout would fire after unmount (and after test teardown).
  useEffect(
    () => () => {
      if (blurTimerRef.current) window.clearTimeout(blurTimerRef.current);
    },
    [],
  );

  useEffect(() => {
    if (!mention.active || mention.query.length < 1) {
      setMention((m) => ({ ...m, results: [] }));
      return;
    }
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(() => {
      searchUsers(mention.query)
        .then((d) =>
          setMention((m) =>
            m.active ? { ...m, results: d.results.slice(0, 6), selectedIndex: 0 } : m,
          ),
        )
        .catch(() => undefined);
    }, 150);
    return () => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
    };
  }, [mention.active, mention.query]);

  function detectMention(value: string, caret: number) {
    const before = value.slice(0, caret);
    const match = /@([A-Za-z0-9_]{1,32})$/.exec(before);
    if (!match) {
      setMention(emptyMention);
      return;
    }
    setMention({
      active: true,
      query: match[1],
      start: caret - match[0].length,
      end: caret,
      results: [],
      selectedIndex: 0,
    });
  }

  function selectMention(user: UserSearchResult) {
    const before = body.slice(0, mention.start);
    const after = body.slice(mention.end);
    const replacement = `@${user.username} `;
    const next = before + replacement + after;
    setBody(next);
    setMention(emptyMention);
    requestAnimationFrame(() => {
      const el = textareaRef.current;
      if (!el) return;
      const pos = (before + replacement).length;
      el.focus();
      el.setSelectionRange(pos, pos);
    });
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (mention.active && mention.results.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setMention((m) => ({ ...m, selectedIndex: (m.selectedIndex + 1) % m.results.length }));
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setMention((m) => ({
          ...m,
          selectedIndex: (m.selectedIndex - 1 + m.results.length) % m.results.length,
        }));
        return;
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        selectMention(mention.results[mention.selectedIndex]);
        return;
      }
      if (e.key === 'Escape') {
        setMention(emptyMention);
        return;
      }
    }
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      void handleSubmit();
    }
  }

  async function handleSubmit() {
    const trimmed = body.trim();
    if (!trimmed) return;
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit(trimmed);
      setBody('');
    } catch (e) {
      // Keep the typed text so the user can retry or copy it.
      setError(
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          t('comments.submitFailed'),
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="relative flex flex-col gap-2">
      <textarea
        ref={textareaRef}
        rows={3}
        value={body}
        autoFocus={autoFocus}
        placeholder={placeholder}
        onChange={(e) => {
          setBody(e.target.value);
          detectMention(e.target.value, e.target.selectionStart ?? e.target.value.length);
        }}
        onKeyDown={handleKeyDown}
        onSelect={(e) => {
          const target = e.target as HTMLTextAreaElement;
          detectMention(target.value, target.selectionStart);
        }}
        onBlur={() => {
          if (blurTimerRef.current) window.clearTimeout(blurTimerRef.current);
          blurTimerRef.current = window.setTimeout(() => setMention(emptyMention), 150);
        }}
        className="resize-y rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-2 text-sm focus:border-[var(--color-accent)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]/30"
      />

      {mention.active && mention.results.length > 0 && (
        <div className="absolute left-0 top-full z-30 mt-1 w-64 overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] shadow-2xl">
          {mention.results.map((u, i) => (
            <button
              key={u.id}
              type="button"
              onMouseDown={(e) => {
                e.preventDefault();
                selectMention(u);
              }}
              className={cn(
                'flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors',
                i === mention.selectedIndex
                  ? 'bg-[var(--color-surface-hover)]'
                  : 'hover:bg-[var(--color-surface-hover)]',
              )}
            >
              <Avatar src={u.avatar} alt={u.username} size="xs" />
              <span className="font-medium">{u.username}</span>
            </button>
          ))}
        </div>
      )}

      {error && <p className="text-sm text-[var(--color-danger)]">{error}</p>}

      <div className="flex justify-end gap-2">
        {onCancel && (
          <Button type="button" variant="ghost" size="sm" onClick={onCancel}>
            Cancel
          </Button>
        )}
        <Button type="button" size="sm" loading={submitting} onClick={handleSubmit}>
          {submitLabel}
        </Button>
      </div>
    </div>
  );
}

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { previewMarkdown } from '@/api/markdown';
import { cn } from '@/lib/cn';

interface MarkdownEditorProps {
  value: string;
  onChange: (value: string) => void;
  rows?: number;
  error?: string;
}

export function MarkdownEditor({ value, onChange, rows = 8, error }: MarkdownEditorProps) {
  const { t } = useTranslation();
  const [tab, setTab] = useState<'write' | 'preview'>('write');
  const [html, setHtml] = useState('');
  const [previewedFor, setPreviewedFor] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function showPreview() {
    setTab('preview');
    if (!value.trim() || previewedFor === value) return;
    setLoading(true);
    try {
      const rendered = await previewMarkdown(value);
      setHtml(rendered);
      setPreviewedFor(value);
    } catch {
      setHtml('');
      setPreviewedFor(null);
    } finally {
      setLoading(false);
    }
  }

  const tabCls = (active: boolean) =>
    cn(
      'rounded-full px-3 py-1 text-[12.5px] font-medium transition',
      active
        ? 'bg-[var(--color-bg-3)] text-[var(--color-text)]'
        : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]',
    );

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <label className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-muted)]">
          {t('editor.bodyLabel')}
        </label>
        <div className="flex gap-0.5 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-1)] p-0.5">
          <button type="button" onClick={() => setTab('write')} className={tabCls(tab === 'write')}>
            {t('editor.write')}
          </button>
          <button type="button" onClick={showPreview} className={tabCls(tab === 'preview')}>
            {t('editor.preview')}
          </button>
        </div>
      </div>

      {tab === 'write' ? (
        <textarea
          rows={rows}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-2 text-sm focus:border-[var(--color-link)] focus:outline-none focus:ring-2 focus:ring-[var(--color-link)]/30"
        />
      ) : (
        <div className="min-h-[10rem] rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-2">
          {loading ? (
            <p className="text-sm text-[var(--color-text-muted)]">{t('editor.rendering')}</p>
          ) : !value.trim() ? (
            <p className="text-sm text-[var(--color-text-dim)]">{t('editor.empty')}</p>
          ) : (
            <div
              className="prose-nexus text-sm text-[var(--color-text)]"
              dangerouslySetInnerHTML={{ __html: html }}
            />
          )}
        </div>
      )}
      {error && <p className="text-xs text-[var(--color-danger)]">{error}</p>}
    </div>
  );
}

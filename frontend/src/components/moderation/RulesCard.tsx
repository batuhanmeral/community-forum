import { useEffect, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { createRule, deleteRule, listRules, updateRule, type RulePayload } from '@/api/communities';
import type { CommunityRule } from '@/features/communities/types';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { fieldErrors } from '@/lib/apiErrors';

const EMPTY_RULE: RulePayload = { short: '', description: '', order: 0 };
const MAX_ORDER = 32767;

// Same ordering as the backend (order, then id).
function sortRules(rules: CommunityRule[]): CommunityRule[] {
  return [...rules].sort((a, b) => a.order - b.order || a.id - b.id);
}

export function RulesCard({ slug }: { slug: string }) {
  const { t } = useTranslation();
  const [rules, setRules] = useState<CommunityRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<RulePayload>(EMPTY_RULE);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [pendingDelete, setPendingDelete] = useState<CommunityRule | null>(null);

  useEffect(() => {
    let cancelled = false;
    listRules(slug)
      .then((r) => {
        if (cancelled) return;
        setRules(sortRules(r));
        setLoadFailed(false);
      })
      .catch(() => {
        if (cancelled) return;
        setRules([]);
        setLoadFailed(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [slug]);

  function resetForm() {
    setEditingId(null);
    setForm(EMPTY_RULE);
    setErrors({});
  }

  function startEdit(rule: CommunityRule) {
    setEditingId(rule.id);
    setForm({ short: rule.short, description: rule.description, order: rule.order });
    setError(null);
    setErrors({});
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const short = form.short.trim();
    if (!short || busy) return;
    setBusy(true);
    setError(null);
    setErrors({});
    try {
      const payload = { ...form, short };
      if (editingId === null) {
        const created = await createRule(slug, payload);
        setRules((arr) => sortRules([...arr, created]));
      } else {
        const updated = await updateRule(slug, editingId, payload);
        setRules((arr) => sortRules(arr.map((r) => (r.id === updated.id ? updated : r))));
      }
      resetForm();
    } catch (err) {
      const fields = fieldErrors(err);
      setErrors(fields);
      if (!fields.short && !fields.description && !fields.order) setError(t('mod.ruleSaveFailed'));
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(id: number) {
    setError(null);
    try {
      await deleteRule(slug, id);
      setRules((arr) => arr.filter((r) => r.id !== id));
      if (editingId === id) resetForm();
    } catch {
      setError(t('mod.ruleSaveFailed'));
    }
  }

  function confirmDelete() {
    if (!pendingDelete) return;
    const { id } = pendingDelete;
    setPendingDelete(null);
    void handleDelete(id);
  }

  return (
    <Card>
      <h2 className="text-base font-semibold tracking-tight">{t('mod.rulesTitle')}</h2>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">{t('mod.rulesHint')}</p>
      {loading ? (
        <p className="mt-3 text-sm text-[var(--color-text-muted)]">{t('mod.loading')}</p>
      ) : loadFailed ? (
        <p className="mt-3 text-sm text-[var(--color-danger)]">{t('mod.loadFailed')}</p>
      ) : rules.length === 0 ? (
        <p className="mt-3 text-sm text-[var(--color-text-muted)]">{t('mod.rulesEmpty')}</p>
      ) : (
        <ol className="mt-3 flex flex-col gap-2">
          {rules.map((rule) => (
            <li
              key={rule.id}
              className="flex flex-wrap items-start justify-between gap-3 rounded-[12px] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-4 py-3"
            >
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-[var(--color-text)]">{rule.short}</p>
                {rule.description && (
                  <p className="mt-0.5 whitespace-pre-wrap text-xs text-[var(--color-text-muted)]">
                    {rule.description}
                  </p>
                )}
              </div>
              <div className="flex shrink-0 gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  aria-label={t('mod.editRuleLabel', { rule: rule.short })}
                  onClick={() => startEdit(rule)}
                >
                  {t('mod.edit')}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={t('mod.deleteRuleLabel', { rule: rule.short })}
                  onClick={() => setPendingDelete(rule)}
                >
                  {t('mod.delete')}
                </Button>
              </div>
            </li>
          ))}
        </ol>
      )}
      <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-3">
        <Input
          name="rule-short"
          label={t('mod.ruleShort')}
          value={form.short}
          maxLength={100}
          error={errors.short}
          onChange={(e) => setForm({ ...form, short: e.target.value })}
        />
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="rule-description"
            className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-muted)]"
          >
            {t('mod.ruleDescription')}
          </label>
          <textarea
            id="rule-description"
            rows={2}
            maxLength={500}
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            aria-describedby={errors.description ? 'rule-description-error' : undefined}
            className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-2 text-sm text-[var(--color-text)] focus:border-[var(--color-accent)] focus:outline-none"
          />
          {errors.description && (
            <p id="rule-description-error" className="text-xs text-[var(--color-danger)]">
              {errors.description}
            </p>
          )}
        </div>
        <Input
          name="rule-order"
          type="number"
          min={0}
          max={MAX_ORDER}
          error={errors.order}
          label={t('mod.ruleOrder')}
          value={form.order}
          onChange={(e) => setForm({ ...form, order: Number(e.target.value) || 0 })}
        />
        <div className="flex items-center gap-2">
          <Button type="submit" loading={busy} disabled={!form.short.trim()}>
            {editingId === null ? t('mod.addRule') : t('mod.saveRule')}
          </Button>
          {editingId !== null && (
            <Button type="button" variant="secondary" onClick={resetForm}>
              {t('mod.cancel')}
            </Button>
          )}
        </div>
        {error && <p className="text-sm text-[var(--color-danger)]">{error}</p>}
      </form>
      <Modal
        open={pendingDelete !== null}
        onClose={() => setPendingDelete(null)}
        title={pendingDelete?.short}
        footer={
          <>
            <Button variant="secondary" onClick={() => setPendingDelete(null)}>
              {t('mod.cancel')}
            </Button>
            <Button variant="danger" onClick={confirmDelete}>
              {t('mod.delete')}
            </Button>
          </>
        }
      >
        <p className="text-sm text-[var(--color-text-muted)]">{t('mod.deleteRuleConfirm')}</p>
      </Modal>
    </Card>
  );
}

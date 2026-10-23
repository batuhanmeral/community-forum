import { useEffect, useState, type FormEvent } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  createFlair,
  deleteFlair,
  getCommunity,
  listFlairs,
  updateCommunity,
} from '@/api/communities';
import { Avatar } from '@/components/ui/Avatar';
import type { Flair } from '@/features/communities/types';
import {
  banUser,
  listModLog,
  setMemberRole,
  type ModLogEntry,
} from '@/api/moderation';
import type { Community, CommunityRole } from '@/features/communities/types';
import { BannedListCard } from '@/components/moderation/BannedListCard';
import { ApprovalQueueCard } from '@/components/moderation/ApprovalQueueCard';
import { ReportQueueCard } from '@/components/moderation/ReportQueueCard';
import { RulesCard } from '@/components/moderation/RulesCard';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { PageTitle } from '@/components/ui/PageTitle';
import { timeAgo } from '@/lib/time';
import { cn } from '@/lib/cn';
import { ArrowLeft, X } from 'lucide-react';

export function ModPage() {
  const { t } = useTranslation();
  const { slug = '' } = useParams<{ slug: string }>();
  const [community, setCommunity] = useState<Community | null>(null);
  const [denied, setDenied] = useState(false);
  const [loading, setLoading] = useState(true);
  const [bansVersion, setBansVersion] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setDenied(false);
    getCommunity(slug)
      .then((c) => {
        if (cancelled) return;
        const isMod = c.my_role === 'admin' || c.my_role === 'moderator';
        if (!isMod) setDenied(true);
        else setCommunity(c);
      })
      .catch(() => {
        if (!cancelled) setDenied(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [slug]);

  if (loading) return <p className="text-sm text-[var(--color-text-muted)]">{t('common.loading')}</p>;
  if (denied || !community) {
    return (
      <Card>
        <PageTitle title={t('mod.accessRequired')} />
        <h2 className="text-lg font-semibold">{t('mod.accessRequired')}</h2>
        <p className="mt-1 text-sm text-[var(--color-text-muted)]">
          {t('mod.accessDenied', { slug })}
        </p>
        <Link to={`/c/${slug}`} className="mt-3 inline-flex items-center gap-1 text-sm text-[var(--color-link)] hover:underline">
          <ArrowLeft className="h-3.5 w-3.5" />
          {t('mod.backToCommunity')}
        </Link>
      </Card>
    );
  }

  const isAdmin = community.my_role === 'admin';

  return (
    <div className="flex flex-col gap-5">
      <PageTitle title={t('mod.tools')} />
      <div>
        <div className="font-mono text-[12px] text-[var(--color-text-dim)]">{t('mod.tools')}</div>
        <h1 className="text-[22px] font-semibold tracking-tight">
          <Link to={`/c/${community.slug}`} className="hover:text-[var(--color-link)]">
            c/{community.slug}
          </Link>
        </h1>
      </div>

      {isAdmin && <CommunitySettingsCard community={community} onUpdated={setCommunity} />}
      <ApprovalQueueCard slug={community.slug} />
      <ReportQueueCard slug={community.slug} />
      {isAdmin && <AutoModCard community={community} onUpdated={setCommunity} />}
      <RulesCard slug={community.slug} />
      <FlairCard slug={community.slug} />
      <BanUserCard slug={community.slug} onBanned={() => setBansVersion((v) => v + 1)} />
      <BannedListCard key={bansVersion} slug={community.slug} />
      {isAdmin && <RoleCard slug={community.slug} />}
      <ModLogCard slug={community.slug} />
    </div>
  );
}

function ModLogCard({ slug }: { slug: string }) {
  const { t } = useTranslation();
  const [entries, setEntries] = useState<ModLogEntry[]>([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    listModLog(slug, 1)
      .then((d) => {
        if (cancelled) return;
        setEntries(d.results);
        setHasMore(Boolean(d.next));
        setPage(1);
      })
      .catch(() => {
        if (!cancelled) setEntries([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [slug]);

  async function loadMore() {
    const next = page + 1;
    const d = await listModLog(slug, next);
    setEntries((arr) => [...arr, ...d.results]);
    setHasMore(Boolean(d.next));
    setPage(next);
  }

  return (
    <Card>
      <h2 className="text-base font-semibold tracking-tight">{t('mod.logTitle')}</h2>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">
        {t('mod.logHint')}
      </p>
      <div className="mt-3 flex flex-col gap-1.5">
        {loading ? (
          <p className="text-sm text-[var(--color-text-muted)]">{t('mod.logLoading')}</p>
        ) : entries.length === 0 ? (
          <p className="text-sm text-[var(--color-text-muted)]">{t('mod.logEmpty')}</p>
        ) : (
          entries.map((e) => (
            <div
              key={e.id}
              className="flex flex-wrap items-baseline gap-x-2 rounded-[10px] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3.5 py-2.5 text-[13px]"
            >
              <span className="font-medium text-[var(--color-text)]">
                {e.actor_username ? `u/${e.actor_username}` : t('mod.automodActor')}
              </span>
              <span className="text-[var(--color-text-soft)]">{t(`mod.log_${e.action}`)}</span>
              {e.target_type === 'post' && e.object_id && (
                <Link to={`/posts/${e.object_id}`} className="text-[var(--color-link)] hover:underline">
                  #{e.object_id}
                </Link>
              )}
              {e.detail && (
                <span className="text-[var(--color-text-muted)]">— {e.detail}</span>
              )}
              <span className="font-mono ml-auto text-[11.5px] text-[var(--color-text-dim)]">
                {timeAgo(e.created_at)}
              </span>
            </div>
          ))
        )}
      </div>
      {hasMore && (
        <button
          type="button"
          onClick={loadMore}
          className="mt-3 text-sm text-[var(--color-link)] hover:underline"
        >
          {t('mod.loadMore')}
        </button>
      )}
    </Card>
  );
}

function AutoModCard({
  community,
  onUpdated,
}: {
  community: Community;
  onUpdated: (c: Community) => void;
}) {
  const { t } = useTranslation();
  const [keywords, setKeywords] = useState(community.banned_keywords ?? '');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const dirty = keywords !== (community.banned_keywords ?? '');

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (busy || !dirty) return;
    setBusy(true);
    setMsg(null);
    try {
      const updated = await updateCommunity(community.slug, { banned_keywords: keywords });
      onUpdated(updated);
      setMsg({ ok: true, text: t('mod.keywordsSaved') });
    } catch {
      setMsg({ ok: false, text: t('mod.keywordsFailed') });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h2 className="text-base font-semibold tracking-tight">{t('mod.automodTitle')}</h2>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">
        {t('mod.automodHint')}
      </p>
      <form onSubmit={handleSubmit} className="mt-3 flex flex-col gap-3">
        <textarea
          value={keywords}
          maxLength={2000}
          rows={4}
          onChange={(e) => setKeywords(e.target.value)}
          placeholder={t('mod.keywordsPlaceholder')}
          className="font-mono w-full rounded-[12px] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3.5 py-2.5 text-[13px] text-[var(--color-text)] placeholder:text-[var(--color-text-dim)] focus:border-[var(--color-link)] focus:outline-none"
        />
        <div className="flex items-center gap-3">
          <Button type="submit" loading={busy} disabled={!dirty}>
            {t('mod.saveKeywords')}
          </Button>
          {msg && (
            <p className={cn('text-sm', msg.ok ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]')}>
              {msg.text}
            </p>
          )}
        </div>
      </form>
    </Card>
  );
}

function CommunitySettingsCard({
  community,
  onUpdated,
}: {
  community: Community;
  onUpdated: (c: Community) => void;
}) {
  const [name, setName] = useState(community.name);
  const [description, setDescription] = useState(community.description);
  const { t } = useTranslation();
  const [isNsfw, setIsNsfw] = useState(community.is_nsfw);
  const [requiresApproval, setRequiresApproval] = useState(community.requires_approval);
  const [avatarFile, setAvatarFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    if (!avatarFile) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(avatarFile);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [avatarFile]);

  const dirty =
    name !== community.name ||
    description !== community.description ||
    isNsfw !== community.is_nsfw ||
    requiresApproval !== community.requires_approval ||
    avatarFile !== null;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (busy || !dirty || !name.trim()) return;
    setBusy(true);
    setMsg(null);
    try {
      const updated = await updateCommunity(community.slug, {
        name: name.trim(),
        description,
        is_nsfw: isNsfw,
        requires_approval: requiresApproval,
        avatar: avatarFile,
      });
      onUpdated(updated);
      setAvatarFile(null);
      setMsg({ ok: true, text: t('mod.settingsSaved') });
    } catch (err) {
      const data = (err as { response?: { data?: Record<string, string[] | string> } })?.response
        ?.data;
      const first = data && Object.values(data)[0];
      setMsg({
        ok: false,
        text: Array.isArray(first) ? first[0] : (first ?? t('mod.settingsFailed')),
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h2 className="text-base font-semibold tracking-tight">{t('mod.settingsTitle')}</h2>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">
        {t('mod.settingsHint', { slug: community.slug })}
      </p>
      <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
        <div className="flex items-center gap-4">
          <Avatar src={preview ?? community.avatar} alt={community.name} size="lg" />
          <label className="cursor-pointer rounded-[var(--radius-control)] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-4 py-2 text-[13px] font-medium text-[var(--color-text-soft)] transition hover:bg-[var(--color-bg-3)] hover:text-[var(--color-text)]">
            {avatarFile ? avatarFile.name : t('mod.changeIcon')}
            <input
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => setAvatarFile(e.target.files?.[0] ?? null)}
            />
          </label>
          {avatarFile && (
            <button
              type="button"
              onClick={() => setAvatarFile(null)}
              className="text-[13px] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            >
              {t('mod.cancel')}
            </button>
          )}
        </div>
        <Input
          name="community-name"
          label={t('communityForm.displayName')}
          value={name}
          maxLength={100}
          onChange={(e) => setName(e.target.value)}
        />
        <div>
          <label className="mb-1.5 block text-[13px] font-medium text-[var(--color-text-soft)]">
            {t('communityForm.description')}
          </label>
          <textarea
            value={description}
            maxLength={500}
            rows={3}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full rounded-[12px] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3.5 py-2.5 text-sm text-[var(--color-text)] placeholder:text-[var(--color-text-dim)] focus:border-[var(--color-link)] focus:outline-none"
            placeholder={t('mod.descriptionPlaceholder')}
          />
        </div>
        <label className="flex cursor-pointer items-center gap-2.5 text-sm text-[var(--color-text-soft)]">
          <input
            type="checkbox"
            checked={isNsfw}
            onChange={(e) => setIsNsfw(e.target.checked)}
            className="h-4 w-4 accent-[var(--color-link)]"
          />
          {t('mod.markNsfw')}
        </label>
        <label className="flex cursor-pointer items-center gap-2.5 text-sm text-[var(--color-text-soft)]">
          <input
            type="checkbox"
            checked={requiresApproval}
            onChange={(e) => setRequiresApproval(e.target.checked)}
            className="h-4 w-4 accent-[var(--color-link)]"
          />
          {t('mod.requiresApproval')}
        </label>
        <div className="flex items-center gap-3">
          <Button type="submit" loading={busy} disabled={!dirty || !name.trim()}>
            {t('mod.saveSettings')}
          </Button>
          {msg && (
            <p className={cn('text-sm', msg.ok ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]')}>
              {msg.text}
            </p>
          )}
        </div>
      </form>
    </Card>
  );
}

function FlairCard({ slug }: { slug: string }) {
  const { t } = useTranslation();
  const [flairs, setFlairs] = useState<Flair[]>([]);
  const [name, setName] = useState('');
  // Flair colours are user data, not theme colours; the picker needs a hex default.
  // eslint-disable-next-line no-restricted-syntax
  const [color, setColor] = useState('#60a5fa');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listFlairs(slug)
      .then(setFlairs)
      .catch(() => setFlairs([]));
  }, [slug]);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    const n = name.trim();
    if (!n || busy) return;
    setBusy(true);
    setError(null);
    try {
      const flair = await createFlair(slug, n, color);
      setFlairs((arr) => [...arr, flair]);
      setName('');
    } catch (err) {
      const data = (err as { response?: { data?: Record<string, string[] | string> } })?.response
        ?.data;
      const first = data && Object.values(data)[0];
      setError(Array.isArray(first) ? first[0] : (first ?? t('mod.flairFailed')));
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(id: number) {
    try {
      await deleteFlair(slug, id);
      setFlairs((arr) => arr.filter((f) => f.id !== id));
    } catch {
      // keep the list as-is; a failed delete just leaves the flair visible
    }
  }

  return (
    <Card>
      <h2 className="text-base font-semibold tracking-tight">{t('mod.flairsTitle')}</h2>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">
        {t('mod.flairsHint')}
      </p>
      {flairs.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {flairs.map((f) => (
            <span
              key={f.id}
              className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[12px] font-medium"
              style={{ color: f.color, borderColor: `${f.color}44`, background: `${f.color}14` }}
            >
              {f.name}
              <button
                type="button"
                onClick={() => handleDelete(f.id)}
                aria-label={t('mod.deleteFlair', { name: f.name })}
                className="opacity-60 transition hover:opacity-100"
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}
      <form onSubmit={handleCreate} className="mt-3 flex flex-wrap items-end gap-2">
        <div className="min-w-[180px] flex-1">
          <Input
            name="flair-name"
            placeholder={t('mod.flairName')}
            value={name}
            maxLength={50}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <input
          type="color"
          value={color}
          onChange={(e) => setColor(e.target.value)}
          aria-label={t('mod.flairColor')}
          className="h-10 w-12 cursor-pointer rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-1"
        />
        <Button type="submit" loading={busy} disabled={!name.trim()}>
          {t('mod.addFlair')}
        </Button>
      </form>
      {error && <p className="mt-2 text-sm text-[var(--color-danger)]">{error}</p>}
    </Card>
  );
}

function BanUserCard({ slug, onBanned }: { slug: string; onBanned: () => void }) {
  const { t } = useTranslation();
  const [username, setUsername] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const u = username.trim();
    if (!u || busy) return;
    setBusy(true);
    setMsg(null);
    try {
      await banUser(slug, u);
      setMsg({ ok: true, text: t('mod.banned', { username: u }) });
      setUsername('');
      onBanned();
    } catch (err) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        t('mod.banFailed');
      setMsg({ ok: false, text: detail });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h2 className="text-base font-semibold tracking-tight">{t('mod.banTitle')}</h2>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">
        {t('mod.banHint')}
      </p>
      <form onSubmit={handleSubmit} className="mt-3 flex flex-wrap items-end gap-2">
        <div className="min-w-[220px] flex-1">
          <Input
            name="ban-username"
            placeholder={t('mod.usernamePlaceholder')}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        </div>
        <Button type="submit" variant="danger" loading={busy} disabled={!username.trim()}>
          {t('mod.banUser')}
        </Button>
      </form>
      {msg && (
        <p className={cn('mt-2 text-sm', msg.ok ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]')}>
          {msg.text}
        </p>
      )}
    </Card>
  );
}

function RoleCard({ slug }: { slug: string }) {
  const { t } = useTranslation();
  const [username, setUsername] = useState('');
  const [role, setRole] = useState<CommunityRole>('moderator');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const u = username.trim();
    if (!u || busy) return;
    setBusy(true);
    setMsg(null);
    try {
      await setMemberRole(slug, u, role);
      setMsg({ ok: true, text: t(`mod.roleSet_${role}`, { username: u }) });
      setUsername('');
    } catch (err) {
      const detail =
        (err as { response?: { data?: { detail?: string; role?: string } } })?.response?.data;
      setMsg({
        ok: false,
        text: detail?.detail ?? detail?.role ?? t('mod.roleFailed'),
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h2 className="text-base font-semibold tracking-tight">{t('mod.rolesTitle')}</h2>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">
        {t('mod.rolesHint')}
      </p>
      <form onSubmit={handleSubmit} className="mt-3 flex flex-wrap items-end gap-2">
        <div className="min-w-[180px] flex-1">
          <Input
            name="role-username"
            placeholder={t('mod.usernamePlaceholder')}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        </div>
        <select
          value={role}
          onChange={(e) => setRole(e.target.value as CommunityRole)}
          className="h-10 rounded-[var(--radius-control)] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 text-sm text-[var(--color-text)] focus:border-[var(--color-link)] focus:outline-none"
        >
          <option value="member">{t('mod.role_member')}</option>
          <option value="moderator">{t('mod.role_moderator')}</option>
          <option value="admin">{t('mod.role_admin')}</option>
        </select>
        <Button type="submit" loading={busy} disabled={!username.trim()}>
          {t('mod.updateRole')}
        </Button>
      </form>
      {msg && (
        <p className={cn('mt-2 text-sm', msg.ok ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]')}>
          {msg.text}
        </p>
      )}
    </Card>
  );
}

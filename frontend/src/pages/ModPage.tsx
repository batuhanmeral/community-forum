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
  dismissReport,
  listModLog,
  listModReports,
  resolveReport,
  setMemberRole,
  type ModLogEntry,
  type Report,
  type ReportStatus,
} from '@/api/moderation';
import type { Community, CommunityRole } from '@/features/communities/types';
import { ApprovalQueueCard } from '@/components/moderation/ApprovalQueueCard';
import { RulesCard } from '@/components/moderation/RulesCard';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { timeAgo } from '@/lib/time';
import { cn } from '@/lib/cn';

const STATUSES: ReportStatus[] = ['open', 'resolved', 'dismissed'];

export function ModPage() {
  const { slug = '' } = useParams<{ slug: string }>();
  const [community, setCommunity] = useState<Community | null>(null);
  const [denied, setDenied] = useState(false);
  const [loading, setLoading] = useState(true);

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

  if (loading) return <p className="text-sm text-[var(--color-text-muted)]">Loading…</p>;
  if (denied || !community) {
    return (
      <Card>
        <h2 className="text-lg font-semibold">Moderator access required</h2>
        <p className="mt-1 text-sm text-[var(--color-text-muted)]">
          You don't have moderator permissions for c/{slug}.
        </p>
        <Link to={`/c/${slug}`} className="mt-3 inline-block text-sm text-[var(--color-accent)] hover:underline">
          ← Back to community
        </Link>
      </Card>
    );
  }

  const isAdmin = community.my_role === 'admin';

  return (
    <div className="flex flex-col gap-5">
      <div>
        <div className="font-mono text-[12px] text-[var(--color-text-dim)]">Moderator tools</div>
        <h1 className="text-[22px] font-semibold tracking-tight">
          <Link to={`/c/${community.slug}`} className="hover:text-[var(--color-accent)]">
            c/{community.slug}
          </Link>
        </h1>
      </div>

      {isAdmin && <CommunitySettingsCard community={community} onUpdated={setCommunity} />}
      <ApprovalQueueCard slug={community.slug} />
      <ReportQueue slug={community.slug} />
      {isAdmin && <AutoModCard community={community} onUpdated={setCommunity} />}
      <RulesCard slug={community.slug} />
      <FlairCard slug={community.slug} />
      <BanUserCard slug={community.slug} />
      {isAdmin && <RoleCard slug={community.slug} />}
      <ModLogCard slug={community.slug} />
    </div>
  );
}

const MOD_LOG_LABELS: Record<ModLogEntry['action'], string> = {
  post_pin: 'pinned a post',
  post_unpin: 'unpinned a post',
  post_approve: 'approved a post',
  post_reject: 'rejected a post',
  post_remove: 'removed a post',
  comment_remove: 'removed a comment',
  user_ban: 'banned a user',
  user_unban: 'unbanned a user',
  role_change: 'changed a member role',
  report_resolve: 'resolved a report',
  report_dismiss: 'dismissed a report',
  automod_hold: 'held a post for review',
};

function ModLogCard({ slug }: { slug: string }) {
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
      <h2 className="text-base font-semibold tracking-tight">Mod log</h2>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">
        Every moderator action in this community, newest first.
      </p>
      <div className="mt-3 flex flex-col gap-1.5">
        {loading ? (
          <p className="text-sm text-[var(--color-text-muted)]">Loading log…</p>
        ) : entries.length === 0 ? (
          <p className="text-sm text-[var(--color-text-muted)]">No mod actions recorded yet.</p>
        ) : (
          entries.map((e) => (
            <div
              key={e.id}
              className="flex flex-wrap items-baseline gap-x-2 rounded-[10px] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3.5 py-2.5 text-[13px]"
            >
              <span className="font-medium text-[var(--color-text)]">
                {e.actor_username ? `u/${e.actor_username}` : 'AutoMod'}
              </span>
              <span className="text-[var(--color-text-soft)]">{MOD_LOG_LABELS[e.action]}</span>
              {e.target_type === 'post' && e.object_id && (
                <Link to={`/posts/${e.object_id}`} className="text-[var(--color-accent)] hover:underline">
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
          className="mt-3 text-sm text-[var(--color-accent)] hover:underline"
        >
          Load more
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
      setMsg({ ok: true, text: 'AutoMod keywords saved.' });
    } catch {
      setMsg({ ok: false, text: 'Could not save keywords.' });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h2 className="text-base font-semibold tracking-tight">AutoMod</h2>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">
        Posts containing any of these keywords are held for moderator approval. One keyword or
        phrase per line. Moderators bypass the filter.
      </p>
      <form onSubmit={handleSubmit} className="mt-3 flex flex-col gap-3">
        <textarea
          value={keywords}
          rows={4}
          onChange={(e) => setKeywords(e.target.value)}
          placeholder={'crypto scam\nbuy followers'}
          className="font-mono w-full rounded-[12px] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3.5 py-2.5 text-[13px] text-[var(--color-text)] placeholder:text-[var(--color-text-dim)] focus:border-[var(--color-accent)] focus:outline-none"
        />
        <div className="flex items-center gap-3">
          <Button type="submit" loading={busy} disabled={!dirty}>
            Save keywords
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
      setMsg({ ok: true, text: 'Community settings saved.' });
    } catch (err) {
      const data = (err as { response?: { data?: Record<string, string[] | string> } })?.response
        ?.data;
      const first = data && Object.values(data)[0];
      setMsg({
        ok: false,
        text: Array.isArray(first) ? first[0] : (first ?? 'Could not save settings.'),
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h2 className="text-base font-semibold tracking-tight">Community settings</h2>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">
        Update the icon, display name, and description of c/{community.slug}.
      </p>
      <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
        <div className="flex items-center gap-4">
          <Avatar src={preview ?? community.avatar} alt={community.name} size="lg" />
          <label className="cursor-pointer rounded-full border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-4 py-2 text-[13px] font-medium text-[var(--color-text-soft)] transition hover:bg-[var(--color-bg-3)] hover:text-[var(--color-text)]">
            {avatarFile ? avatarFile.name : 'Change icon…'}
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
              Cancel
            </button>
          )}
        </div>
        <Input
          name="community-name"
          label="Display name"
          value={name}
          maxLength={100}
          onChange={(e) => setName(e.target.value)}
        />
        <div>
          <label className="mb-1.5 block text-[13px] font-medium text-[var(--color-text-soft)]">
            Description
          </label>
          <textarea
            value={description}
            maxLength={500}
            rows={3}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full rounded-[12px] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3.5 py-2.5 text-sm text-[var(--color-text)] placeholder:text-[var(--color-text-dim)] focus:border-[var(--color-accent)] focus:outline-none"
            placeholder="What is this community about?"
          />
        </div>
        <label className="flex cursor-pointer items-center gap-2.5 text-sm text-[var(--color-text-soft)]">
          <input
            type="checkbox"
            checked={isNsfw}
            onChange={(e) => setIsNsfw(e.target.checked)}
            className="h-4 w-4 accent-[var(--color-accent)]"
          />
          Mark community as NSFW (18+)
        </label>
        <label className="flex cursor-pointer items-center gap-2.5 text-sm text-[var(--color-text-soft)]">
          <input
            type="checkbox"
            checked={requiresApproval}
            onChange={(e) => setRequiresApproval(e.target.checked)}
            className="h-4 w-4 accent-[var(--color-accent)]"
          />
          {t('mod.requiresApproval')}
        </label>
        <div className="flex items-center gap-3">
          <Button type="submit" loading={busy} disabled={!dirty || !name.trim()}>
            Save settings
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

function ReportQueue({ slug }: { slug: string }) {
  const [status, setStatus] = useState<ReportStatus>('open');
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listModReports(slug, status)
      .then((r) => {
        if (!cancelled) setReports(r);
      })
      .catch(() => {
        if (!cancelled) setReports([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [slug, status]);

  async function act(id: number, kind: 'resolve' | 'dismiss') {
    setBusyId(id);
    try {
      if (kind === 'resolve') await resolveReport(slug, id);
      else await dismissReport(slug, id);
      // Drop it from the current (open) list once actioned.
      setReports((arr) => arr.filter((r) => r.id !== id));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-semibold tracking-tight">Report queue</h2>
        <div className="flex gap-0.5 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-1)] p-1">
          {STATUSES.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setStatus(s)}
              className={cn(
                'rounded-full px-3.5 py-1.5 text-[13px] font-medium capitalize transition',
                status === s
                  ? 'bg-[var(--color-bg-3)] text-[var(--color-text)] shadow-[0_1px_0_rgba(255,255,255,0.04),inset_0_1px_0_rgba(255,255,255,0.04)]'
                  : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]',
              )}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-4 flex flex-col gap-2.5">
        {loading ? (
          <p className="text-sm text-[var(--color-text-muted)]">Loading reports…</p>
        ) : reports.length === 0 ? (
          <p className="text-sm text-[var(--color-text-muted)]">No {status} reports.</p>
        ) : (
          reports.map((r) => (
            <div
              key={r.id}
              className="flex flex-wrap items-start justify-between gap-3 rounded-[12px] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-4 py-3"
            >
              <div className="min-w-0 flex-1">
                <div className="font-mono mb-1 flex flex-wrap items-center gap-2 text-[11.5px] text-[var(--color-text-dim)]">
                  <span className="rounded-full border border-[var(--color-border)] bg-[var(--color-bg-3)] px-2 py-0.5 capitalize text-[var(--color-text-soft)]">
                    {r.target_type}
                  </span>
                  {r.target_type === 'post' ? (
                    <Link to={`/posts/${r.object_id}`} className="text-[var(--color-accent)] hover:underline">
                      #{r.object_id}
                    </Link>
                  ) : (
                    <span>#{r.object_id}</span>
                  )}
                  <span>·</span>
                  <span>by u/{r.reporter_username}</span>
                  <span>·</span>
                  <span>{timeAgo(r.created_at)}</span>
                </div>
                <p className="text-sm text-[var(--color-text-soft)]">{r.reason}</p>
              </div>
              {r.status === 'open' && (
                <div className="flex shrink-0 gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => act(r.id, 'dismiss')}
                    loading={busyId === r.id}
                  >
                    Dismiss
                  </Button>
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => act(r.id, 'resolve')}
                    loading={busyId === r.id}
                  >
                    Resolve
                  </Button>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </Card>
  );
}

function FlairCard({ slug }: { slug: string }) {
  const [flairs, setFlairs] = useState<Flair[]>([]);
  const [name, setName] = useState('');
  const [color, setColor] = useState('#61dafb');
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
      setError(Array.isArray(first) ? first[0] : (first ?? 'Could not create flair.'));
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
      <h2 className="text-base font-semibold tracking-tight">Post flairs</h2>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">
        Flairs help members categorize their posts.
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
                aria-label={`Delete flair ${f.name}`}
                className="opacity-60 transition hover:opacity-100"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3 w-3">
                  <path d="M6 6l12 12M6 18 18 6" />
                </svg>
              </button>
            </span>
          ))}
        </div>
      )}
      <form onSubmit={handleCreate} className="mt-3 flex flex-wrap items-end gap-2">
        <div className="min-w-[180px] flex-1">
          <Input
            name="flair-name"
            placeholder="Flair name"
            value={name}
            maxLength={50}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <input
          type="color"
          value={color}
          onChange={(e) => setColor(e.target.value)}
          aria-label="Flair color"
          className="h-10 w-12 cursor-pointer rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-1"
        />
        <Button type="submit" loading={busy} disabled={!name.trim()}>
          Add flair
        </Button>
      </form>
      {error && <p className="mt-2 text-sm text-[var(--color-danger)]">{error}</p>}
    </Card>
  );
}

function BanUserCard({ slug }: { slug: string }) {
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
      setMsg({ ok: true, text: `u/${u} has been banned from this community.` });
      setUsername('');
    } catch (err) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Could not ban this user.';
      setMsg({ ok: false, text: detail });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h2 className="text-base font-semibold tracking-tight">Ban a member</h2>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">
        Banned members can no longer post or comment in this community.
      </p>
      <form onSubmit={handleSubmit} className="mt-3 flex flex-wrap items-end gap-2">
        <div className="min-w-[220px] flex-1">
          <Input
            name="ban-username"
            placeholder="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        </div>
        <Button type="submit" variant="danger" loading={busy} disabled={!username.trim()}>
          Ban user
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
      setMsg({ ok: true, text: `u/${u} is now a ${role}.` });
      setUsername('');
    } catch (err) {
      const detail =
        (err as { response?: { data?: { detail?: string; role?: string } } })?.response?.data;
      setMsg({
        ok: false,
        text: detail?.detail ?? detail?.role ?? 'Could not update this member’s role.',
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h2 className="text-base font-semibold tracking-tight">Manage moderators</h2>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">
        Promote a member to moderator or admin, or demote them back to member.
      </p>
      <form onSubmit={handleSubmit} className="mt-3 flex flex-wrap items-end gap-2">
        <div className="min-w-[180px] flex-1">
          <Input
            name="role-username"
            placeholder="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        </div>
        <select
          value={role}
          onChange={(e) => setRole(e.target.value as CommunityRole)}
          className="h-10 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 text-sm text-[var(--color-text)] focus:border-[var(--color-accent)] focus:outline-none"
        >
          <option value="member">Member</option>
          <option value="moderator">Moderator</option>
          <option value="admin">Admin</option>
        </select>
        <Button type="submit" loading={busy} disabled={!username.trim()}>
          Update role
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

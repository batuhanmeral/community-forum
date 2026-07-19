import { useEffect, useState, type FormEvent } from 'react';
import { Link, useParams } from 'react-router-dom';
import { getCommunity } from '@/api/communities';
import {
  banUser,
  dismissReport,
  listModReports,
  resolveReport,
  setMemberRole,
  type Report,
  type ReportStatus,
} from '@/api/moderation';
import type { Community, CommunityRole } from '@/features/communities/types';
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

      <ReportQueue slug={community.slug} />
      <BanUserCard slug={community.slug} />
      {isAdmin && <RoleCard slug={community.slug} />}
    </div>
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

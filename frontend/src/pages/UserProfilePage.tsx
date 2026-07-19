import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { getUserProfile, type UserProfile } from '@/api/users';
import { useAppSelector } from '@/app/hooks';
import { Avatar } from '@/components/ui/Avatar';
import { Card } from '@/components/ui/Card';
import { FollowButton } from '@/components/follow/FollowButton';
import { FollowListModal } from '@/components/follow/FollowListModal';
import { ReportModal } from '@/components/moderation/ReportModal';

export function UserProfilePage() {
  const { username = '' } = useParams<{ username: string }>();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [listMode, setListMode] = useState<'followers' | 'following' | null>(null);
  const [reporting, setReporting] = useState(false);
  const myUsername = useAppSelector((s) => s.auth.user?.username);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setNotFound(false);
    getUserProfile(username)
      .then((p) => {
        if (!cancelled) setProfile(p);
      })
      .catch(() => {
        if (!cancelled) setNotFound(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [username]);

  if (loading) return <p className="text-sm text-[var(--color-text-muted)]">Loading…</p>;
  if (notFound || !profile) {
    return (
      <Card>
        <h2 className="text-lg font-semibold">User not found</h2>
        <p className="mt-1 text-sm text-[var(--color-text-muted)]">
          No user named u/{username}.
        </p>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <div className="flex items-start gap-4">
          <Avatar src={profile.avatar} alt={profile.username} size="lg" />
          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <h1 className="text-xl font-bold tracking-tight">u/{profile.username}</h1>
                <p className="mt-0.5 text-xs text-[var(--color-text-dim)]">
                  Joined {new Date(profile.date_joined).toLocaleDateString()}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <FollowButton
                  username={profile.username}
                  initialFollowing={profile.is_following}
                  onChange={(following) =>
                    setProfile((p) =>
                      p
                        ? {
                            ...p,
                            is_following: following,
                            followers_count: p.followers_count + (following ? 1 : -1),
                          }
                        : p,
                    )
                  }
                />
                {myUsername && myUsername !== profile.username && (
                  <button
                    type="button"
                    onClick={() => setReporting(true)}
                    title="Report user"
                    aria-label="Report user"
                    className="grid h-9 w-9 place-items-center rounded-full border border-[var(--color-border)] text-[var(--color-text-muted)] transition hover:border-[var(--color-danger)] hover:text-[var(--color-danger)]"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" className="h-[17px] w-[17px]">
                      <path d="M4 21V4h12l-2 4 2 4H4" />
                    </svg>
                  </button>
                )}
              </div>
            </div>
            {profile.bio && (
              <p className="mt-2 text-sm text-[var(--color-text-soft)] whitespace-pre-wrap">
                {profile.bio}
              </p>
            )}
          </div>
        </div>

        <div className="mt-5 grid grid-cols-3 gap-3 border-t border-[var(--color-border)] pt-4">
          <KarmaStat label="Total karma" value={profile.total_karma} accent />
          <KarmaStat label="Post karma" value={profile.post_karma} />
          <KarmaStat label="Comment karma" value={profile.comment_karma} />
        </div>

        <div className="mt-3 grid grid-cols-2 gap-3">
          <button
            type="button"
            onClick={() => setListMode('followers')}
            className="rounded-[10px] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-2.5 text-left transition hover:border-[var(--color-border-strong)] hover:bg-[var(--color-bg-3)]"
          >
            <div className="font-mono text-[18px] font-medium tracking-tight text-[var(--color-text)]">
              {profile.followers_count.toLocaleString()}
            </div>
            <div className="mt-0.5 text-[10.5px] uppercase tracking-[0.08em] text-[var(--color-text-dim)]">
              Followers
            </div>
          </button>
          <button
            type="button"
            onClick={() => setListMode('following')}
            className="rounded-[10px] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-2.5 text-left transition hover:border-[var(--color-border-strong)] hover:bg-[var(--color-bg-3)]"
          >
            <div className="font-mono text-[18px] font-medium tracking-tight text-[var(--color-text)]">
              {profile.following_count.toLocaleString()}
            </div>
            <div className="mt-0.5 text-[10.5px] uppercase tracking-[0.08em] text-[var(--color-text-dim)]">
              Following
            </div>
          </button>
        </div>
      </Card>

      <Card>
        <p className="text-sm text-[var(--color-text-muted)]">
          Posts &amp; comments by u/{profile.username} will appear here.
        </p>
      </Card>

      <FollowListModal
        open={listMode !== null}
        onClose={() => setListMode(null)}
        username={profile.username}
        mode={listMode ?? 'followers'}
      />

      <ReportModal
        open={reporting}
        onClose={() => setReporting(false)}
        target="user"
        objectId={profile.id}
        label="user"
      />
    </div>
  );
}

interface KarmaStatProps {
  label: string;
  value: number;
  accent?: boolean;
}

function KarmaStat({ label, value, accent }: KarmaStatProps) {
  return (
    <div className="rounded-[10px] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-2.5">
      <div
        className={
          accent
            ? 'font-mono text-[20px] font-medium tracking-tight text-[var(--color-accent)]'
            : 'font-mono text-[18px] font-medium tracking-tight text-[var(--color-text)]'
        }
      >
        {value.toLocaleString()}
      </div>
      <div className="mt-0.5 text-[10.5px] uppercase tracking-[0.08em] text-[var(--color-text-dim)]">
        {label}
      </div>
    </div>
  );
}

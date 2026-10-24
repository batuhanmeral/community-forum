import { useEffect, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';
import {
  getUserComments,
  getUserPosts,
  getUserProfile,
  updateProfile,
  type UserProfile,
} from '@/api/users';
import type { Post } from '@/features/posts/types';
import type { Comment } from '@/features/comments/types';
import { useAppDispatch, useAppSelector } from '@/app/hooks';
import { setUser } from '@/features/auth/authSlice';
import { Avatar } from '@/components/ui/Avatar';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Modal } from '@/components/ui/Modal';
import { PageTitle } from '@/components/ui/PageTitle';
import { deletedBodyKey } from '@/lib/deletedBody';
import { PostCard } from '@/components/posts/PostCard';
import { blockUser, unblockUser } from '@/api/follow';
import { FollowButton } from '@/components/follow/FollowButton';
import { FollowListModal } from '@/components/follow/FollowListModal';
import { ReportModal } from '@/components/moderation/ReportModal';
import { fieldErrors } from '@/lib/apiErrors';
import { timeAgo } from '@/lib/time';
import { cn } from '@/lib/cn';
import { countriesByName, countryFlag, countryName } from '@/lib/countries';
import { ArrowBigUp, Flag } from 'lucide-react';

export function UserProfilePage() {
  const { t, i18n } = useTranslation();
  const { username = '' } = useParams<{ username: string }>();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [listMode, setListMode] = useState<'followers' | 'following' | null>(null);
  const [reporting, setReporting] = useState(false);
  const [editing, setEditing] = useState(false);
  const [blockBusy, setBlockBusy] = useState(false);
  const myUsername = useAppSelector((s) => s.auth.user?.username);
  const isOwnProfile = Boolean(myUsername) && myUsername === profile?.username;

  async function handleBlockToggle() {
    if (!profile || blockBusy) return;
    setBlockBusy(true);
    try {
      if (profile.is_blocked) {
        await unblockUser(profile.username);
        setProfile((p) => (p ? { ...p, is_blocked: false } : p));
      } else {
        await blockUser(profile.username);
        // Blocking severs follows in both directions server-side.
        setProfile((p) =>
          p
            ? {
                ...p,
                is_blocked: true,
                is_following: false,
                followers_count: p.followers_count - (p.is_following ? 1 : 0),
              }
            : p,
        );
      }
    } finally {
      setBlockBusy(false);
    }
  }

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

  if (loading) {
    return (
      <>
        <PageTitle />
        <p className="text-sm text-[var(--color-text-muted)]">{t('common.loading')}</p>
      </>
    );
  }
  if (notFound || !profile) {
    return (
      <Card>
        <PageTitle title={t('profile.notFoundTitle')} />
        <h2 className="text-lg font-semibold">{t('profile.notFoundTitle')}</h2>
        <p className="mt-1 text-sm text-[var(--color-text-muted)]">
          {t('profile.notFoundBody', { username })}
        </p>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <PageTitle title={`u/${profile.username}`} />
      <Card>
        <div className="flex items-start gap-4">
          <Avatar src={profile.avatar} alt={profile.username} size="lg" />
          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <h1 className="text-xl font-bold tracking-tight">u/{profile.username}</h1>
                <p className="mt-0.5 text-xs text-[var(--color-text-dim)]">
                  {profile.country && (
                    <span className="mr-2 text-[var(--color-text-muted)]">
                      <span aria-hidden="true">{countryFlag(profile.country)}</span>{' '}
                      {countryName(profile.country, i18n.language)}
                    </span>
                  )}
                  {t('profile.joined', { date: new Date(profile.date_joined).toLocaleDateString(i18n.language) })}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {isOwnProfile ? (
                  <Button variant="secondary" size="sm" onClick={() => setEditing(true)}>
                    {t('profile.editProfile')}
                  </Button>
                ) : (
                  <>
                    {!profile.is_blocked && (
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
                    )}
                    {myUsername && (
                      <Button
                        variant={profile.is_blocked ? 'secondary' : 'ghost'}
                        size="sm"
                        loading={blockBusy}
                        onClick={handleBlockToggle}
                      >
                        {profile.is_blocked ? t('follow.unblock') : t('follow.block')}
                      </Button>
                    )}
                    {myUsername && (
                      <button
                        type="button"
                        onClick={() => setReporting(true)}
                        title={t('profile.reportUser')}
                        aria-label={t('profile.reportUser')}
                        className="grid h-9 w-9 place-items-center rounded-[var(--radius-control)] border border-[var(--color-border)] text-[var(--color-text-muted)] transition hover:border-[var(--color-danger)] hover:text-[var(--color-danger)]"
                      >
                        <Flag className="h-[17px] w-[17px]" />
                      </button>
                    )}
                  </>
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
          <KarmaStat label={t('profile.totalKarma')} value={profile.total_karma} accent />
          <KarmaStat label={t('profile.postKarma')} value={profile.post_karma} />
          <KarmaStat label={t('profile.commentKarma')} value={profile.comment_karma} />
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
              {t('profile.followers')}
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
              {t('profile.following')}
            </div>
          </button>
        </div>
      </Card>

      <ProfileContent username={profile.username} />

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
      />

      {isOwnProfile && (
        <ProfileEditModal
          open={editing}
          onClose={() => setEditing(false)}
          initialBio={profile.bio}
          initialCountry={profile.country}
          onSaved={(updated) => {
            setProfile((p) => (p ? { ...p, ...updated } : p));
            setEditing(false);
          }}
        />
      )}
    </div>
  );
}

type ProfileTab = 'posts' | 'comments';

function ProfileContent({ username }: { username: string }) {
  const { t } = useTranslation();
  const [tab, setTab] = useState<ProfileTab>('posts');
  const [posts, setPosts] = useState<Post[]>([]);
  const [comments, setComments] = useState<Comment[]>([]);
  const [loading, setLoading] = useState(true);

  // Reset to the Posts tab whenever the profile changes.
  useEffect(() => {
    setTab('posts');
  }, [username]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const req = tab === 'posts' ? getUserPosts(username) : getUserComments(username);
    req
      .then((d) => {
        if (cancelled) return;
        if (tab === 'posts') setPosts(d.results as Post[]);
        else setComments(d.results as Comment[]);
      })
      .catch(() => {
        if (cancelled) return;
        if (tab === 'posts') setPosts([]);
        else setComments([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [tab, username]);

  const items = tab === 'posts' ? posts : comments;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex gap-0.5 self-start rounded-[var(--radius-control)] border border-[var(--color-border)] bg-[var(--color-bg-1)] p-1">
        {(['posts', 'comments'] as ProfileTab[]).map((name) => (
          <button
            key={name}
            type="button"
            onClick={() => setTab(name)}
            className={cn(
              'rounded-[var(--radius-control-inner)] px-4 py-1.5 text-[13px] font-medium transition',
              tab === name
                ? 'bg-[var(--color-bg-3)] text-[var(--color-text)]'
                : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]',
            )}
          >
            {t(`profile.tab_${name}`)}
          </button>
        ))}
      </div>

      {loading ? (
        <Card>
          <p className="text-sm text-[var(--color-text-muted)]">{t('common.loading')}</p>
        </Card>
      ) : items.length === 0 ? (
        <Card>
          <p className="text-sm text-[var(--color-text-muted)]">
            {t(tab === 'posts' ? 'profile.noPosts' : 'profile.noComments', { username })}
          </p>
        </Card>
      ) : tab === 'posts' ? (
        posts.map((p) => <PostCard key={p.id} post={p} />)
      ) : (
        comments.map((c) => <ProfileCommentRow key={c.id} comment={c} />)
      )}
    </div>
  );
}

function ProfileCommentRow({ comment }: { comment: Comment }) {
  const { t } = useTranslation();
  return (
    <Link
      to={`/posts/${comment.post}`}
      className="block rounded-[14px] border border-[var(--color-border)] bg-[var(--color-bg-1)] px-4 py-3 transition hover:border-[var(--color-border-strong)]"
    >
      <div className="font-mono mb-1 flex items-center gap-2 text-[11.5px] text-[var(--color-text-dim)]">
        <span>{t('profile.commentLabel')}</span>
        <span>·</span>
        <span>{timeAgo(comment.created_at)}</span>
        {comment.edited_at && <span className="italic">{t('post.edited')}</span>}
        <span>·</span>
        <span className="inline-flex items-center gap-0.5 text-[var(--color-text-soft)]">
          <ArrowBigUp className="h-3.5 w-3.5" />
          {comment.score.toLocaleString()}
        </span>
      </div>
      <p className="line-clamp-3 text-sm text-[var(--color-text-soft)] whitespace-pre-wrap">
        {comment.is_deleted ? t(deletedBodyKey(comment.body)) : comment.body}
      </p>
    </Link>
  );
}

interface ProfileEditModalProps {
  open: boolean;
  onClose: () => void;
  initialBio: string;
  initialCountry: string;
  onSaved: (updated: { bio: string; country: string; avatar: string | null }) => void;
}

function ProfileEditModal({ open, onClose, initialBio, initialCountry, onSaved }: ProfileEditModalProps) {
  const { t, i18n } = useTranslation();
  const dispatch = useAppDispatch();
  const [bio, setBio] = useState(initialBio);
  const [country, setCountry] = useState(initialCountry);
  const [avatar, setAvatar] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (open) {
      setBio(initialBio);
      setCountry(initialCountry);
      setAvatar(null);
      setPreview(null);
      setError(null);
      setErrors({});
      setSaving(false);
    }
  }, [open, initialBio, initialCountry]);

  function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    setAvatar(file);
    setPreview(file ? URL.createObjectURL(file) : null);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (saving) return;
    setSaving(true);
    setError(null);
    setErrors({});
    try {
      const updated = await updateProfile({ bio, country, avatar });
      dispatch(setUser(updated));
      onSaved({ bio: updated.bio, country: updated.country, avatar: updated.avatar });
    } catch (err) {
      const fields = fieldErrors(err);
      setErrors(fields);
      if (!fields.bio && !fields.country && !fields.avatar) setError(t('profile.saveFailed'));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t('profile.editProfile')}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button onClick={handleSubmit} loading={saving}>
            {t('common.save')}
          </Button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="flex items-center gap-4">
          <Avatar src={preview} alt={t('profile.avatarPreview')} size="lg" />
          <label className="cursor-pointer rounded-[var(--radius-control)] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3.5 py-2 text-[13px] font-medium text-[var(--color-text-soft)] transition hover:bg-[var(--color-bg-3)] hover:text-[var(--color-text)]">
            {avatar ? t('profile.changeImage') : t('profile.uploadAvatar')}
            <input type="file" accept="image/*" onChange={onFile} className="hidden" />
          </label>
        </div>
        {errors.avatar && <p className="text-xs text-[var(--color-danger)]">{errors.avatar}</p>}
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="profile-bio"
            className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-muted)]">
            {t('profile.bio')}
          </label>
          <textarea
            id="profile-bio"
            aria-describedby={errors.bio ? 'profile-bio-error' : undefined}
            rows={4}
            value={bio}
            onChange={(e) => setBio(e.target.value)}
            maxLength={500}
            placeholder={t('profile.bioPlaceholder')}
            className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-2 text-sm focus:border-[var(--color-link)] focus:outline-none focus:ring-2 focus:ring-[var(--color-link)]/30"
          />
          <span className="font-mono self-end text-[11px] text-[var(--color-text-dim)]">
            {bio.length}/500
          </span>
          {errors.bio && (
            <p id="profile-bio-error" className="text-xs text-[var(--color-danger)]">
              {errors.bio}
            </p>
          )}
        </div>
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="profile-country"
            className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-muted)]">
            {t('profile.country')}
          </label>
          <select
            id="profile-country"
            aria-describedby={errors.country ? 'profile-country-error' : undefined}
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-2 text-sm focus:border-[var(--color-link)] focus:outline-none focus:ring-2 focus:ring-[var(--color-link)]/30"
          >
            <option value="">{t('profile.noCountry')}</option>
            {countriesByName(i18n.language).map((c) => (
              <option key={c.code} value={c.code}>
                {countryFlag(c.code)} {c.name}
              </option>
            ))}
          </select>
          {errors.country && (
            <p id="profile-country-error" className="text-xs text-[var(--color-danger)]">
              {errors.country}
            </p>
          )}
        </div>
        {error && <p className="text-sm text-[var(--color-danger)]">{error}</p>}
      </form>
    </Modal>
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
            ? 'font-mono text-[20px] font-medium tracking-tight text-[var(--color-link)]'
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

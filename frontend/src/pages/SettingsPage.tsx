import { useEffect, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { AxiosError } from 'axios';
import { resendVerificationEmail } from '@/api/auth';
import { changePassword, deactivateAccount, updatePreferences } from '@/api/users';
import { listBlocked, unblockUser, type FollowUser } from '@/api/follow';
import { logout, setTokens, setUser } from '@/features/auth/authSlice';
import { useAppDispatch, useAppSelector } from '@/app/hooks';
import { Avatar } from '@/components/ui/Avatar';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { PageTitle } from '@/components/ui/PageTitle';
import { cn } from '@/lib/cn';
import { LANGUAGES, type Language } from '@/i18n';

export function SettingsPage() {
  const { t } = useTranslation();
  const user = useAppSelector((s) => s.auth.user);

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-5">
      <PageTitle title={t('titles.settings')} />
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{t('settings.title')}</h1>
        {user && (
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">
            {t('settings.signedInAs')} u/{user.username}
          </p>
        )}
      </div>

      <PreferencesCard />
      <PasswordCard />
      <BlockedUsersCard />
      <DangerZoneCard />
    </div>
  );
}

function PreferencesCard() {
  const { t, i18n } = useTranslation();
  const user = useAppSelector((s) => s.auth.user);
  const dispatch = useAppDispatch();
  const [busy, setBusy] = useState(false);
  const showNsfw = user?.show_nsfw ?? false;

  async function toggleNsfw() {
    if (busy || !user) return;
    setBusy(true);
    try {
      const updated = await updatePreferences({ show_nsfw: !showNsfw });
      dispatch(setUser(updated));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h2 className="text-base font-semibold tracking-tight">{t('settings.preferences')}</h2>
      <label className="mt-3 flex cursor-pointer items-center justify-between gap-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-2.5">
        <span className="text-sm">
          <span className="font-medium">{t('nsfw.reveal')}</span>
          <span className="ml-2 text-[var(--color-text-muted)]">{t('settings.showNsfwHint')}</span>
        </span>
        <button
          type="button"
          role="switch"
          aria-checked={showNsfw}
          disabled={busy}
          onClick={toggleNsfw}
          className={cn(
            'relative inline-block h-5 w-9 shrink-0 rounded-full transition-colors disabled:opacity-60',
            showNsfw ? 'bg-[var(--color-danger)]' : 'bg-[var(--color-bg-3)]',
          )}
        >
          <span
            className={cn(
              'absolute top-1 h-3 w-3 rounded-full bg-[var(--color-text)] transition-all',
              showNsfw ? 'left-5' : 'left-1',
            )}
          />
        </button>
      </label>
      <label className="mt-2.5 flex items-center justify-between gap-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-2.5">
        <span className="text-sm">
          <span className="font-medium">{t('settings.language')}</span>
          <span className="ml-2 text-[var(--color-text-muted)]">{t('settings.languageHint')}</span>
        </span>
        <select
          value={i18n.language}
          onChange={(e) => i18n.changeLanguage(e.target.value as Language)}
          className="h-9 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-3)] px-3 text-sm text-[var(--color-text)] focus:border-[var(--color-link)] focus:outline-none"
        >
          {LANGUAGES.map((l) => (
            <option key={l.code} value={l.code}>
              {l.label}
            </option>
          ))}
        </select>
      </label>
      {user && <EmailVerificationRow verified={user.email_verified} email={user.email} />}
    </Card>
  );
}

function EmailVerificationRow({ verified, email }: { verified: boolean; email: string }) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);

  async function resend() {
    if (busy) return;
    setBusy(true);
    try {
      await resendVerificationEmail();
      setSent(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-2.5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-2.5">
      <span className="text-sm">
        <span className="font-medium">{t('settings.emailStatus')}</span>
        <span className="ml-2 text-[var(--color-text-muted)]">{email}</span>
        <span
          className={cn(
            'ml-2 rounded-full border px-2 py-0.5 text-[11px] font-medium',
            verified
              ? 'border-[var(--color-link-border)] bg-[var(--color-link)]/8 text-[var(--color-link)]'
              : 'border-[var(--color-danger)]/20 bg-[var(--color-danger-dim)] text-[var(--color-danger)]',
          )}
        >
          {verified ? t('settings.emailVerified') : t('settings.emailUnverified')}
        </span>
      </span>
      {!verified &&
        (sent ? (
          <span className="text-sm text-[var(--color-success)]">
            {t('settings.verificationSent')}
          </span>
        ) : (
          <button
            type="button"
            onClick={resend}
            disabled={busy}
            className="text-sm text-[var(--color-link)] underline underline-offset-2 hover:text-[var(--color-link-hover)] disabled:opacity-60"
          >
            {t('settings.resendVerification')}
          </button>
        ))}
    </div>
  );
}

function PasswordCard() {
  const { t } = useTranslation();
  const dispatch = useAppDispatch();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    if (next !== confirm) {
      setMsg({ ok: false, text: t('settings.passwordMismatch') });
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      const tokens = await changePassword(current, next);
      dispatch(setTokens(tokens));
      setMsg({ ok: true, text: t('settings.passwordUpdated') });
      setCurrent('');
      setNext('');
      setConfirm('');
    } catch (err) {
      const ax = err as AxiosError<Record<string, string[] | string>>;
      const data = ax.response?.data ?? {};
      const first = Object.values(data)[0];
      setMsg({
        ok: false,
        text: Array.isArray(first) ? first[0] : (String(first ?? '') || t('settings.passwordUpdateFailed')),
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h2 className="text-base font-semibold tracking-tight">{t('settings.passwordTitle')}</h2>
      <form onSubmit={handleSubmit} className="mt-3 flex flex-col gap-3">
        <Input
          name="current-password"
          type="password"
          label={t('settings.currentPassword')}
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          autoComplete="current-password"
          required
        />
        <Input
          name="new-password"
          type="password"
          label={t('auth.newPassword')}
          value={next}
          onChange={(e) => setNext(e.target.value)}
          autoComplete="new-password"
          required
        />
        <Input
          name="confirm-password"
          type="password"
          label={t('settings.confirmNewPassword')}
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          autoComplete="new-password"
          required
        />
        <div className="flex items-center justify-between gap-3">
          {msg ? (
            <p className={cn('text-sm', msg.ok ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]')}>
              {msg.text}
            </p>
          ) : (
            <span />
          )}
          <Button type="submit" loading={busy} disabled={!current || !next || !confirm}>
            {t('settings.updatePassword')}
          </Button>
        </div>
      </form>
    </Card>
  );
}

function BlockedUsersCard() {
  const { t } = useTranslation();
  const [users, setUsers] = useState<FollowUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);

  useEffect(() => {
    listBlocked()
      .then((d) => setUsers(d.results))
      .catch(() => setUsers([]))
      .finally(() => setLoading(false));
  }, []);

  async function handleUnblock(u: FollowUser) {
    setBusyId(u.id);
    try {
      await unblockUser(u.username);
      setUsers((arr) => arr.filter((x) => x.id !== u.id));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Card>
      <h2 className="text-base font-semibold tracking-tight">{t('settings.blockedTitle')}</h2>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">{t('settings.blockedHint')}</p>
      <div className="mt-3 flex flex-col gap-2">
        {loading ? (
          <p className="text-sm text-[var(--color-text-muted)]">{t('common.loading')}</p>
        ) : users.length === 0 ? (
          <p className="text-sm text-[var(--color-text-dim)]">{t('settings.blockedEmpty')}</p>
        ) : (
          users.map((u) => (
            <div
              key={u.id}
              className="flex items-center justify-between gap-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-2"
            >
              <div className="flex min-w-0 items-center gap-2.5">
                <Avatar src={u.avatar} alt={u.username} size="sm" />
                <span className="truncate text-sm font-medium">u/{u.username}</span>
              </div>
              <Button
                variant="secondary"
                size="sm"
                loading={busyId === u.id}
                onClick={() => handleUnblock(u)}
              >
                {t('follow.unblock')}
              </Button>
            </div>
          ))
        )}
      </div>
    </Card>
  );
}

function DangerZoneCard() {
  const { t } = useTranslation();
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);

  async function handleDeactivate() {
    if (busy) return;
    setBusy(true);
    try {
      await deactivateAccount();
      dispatch(logout());
      navigate('/', { replace: true });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h2 className="text-base font-semibold tracking-tight text-[var(--color-danger)]">
        {t('settings.dangerTitle')}
      </h2>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">{t('settings.dangerHint')}</p>
      <div className="mt-3 flex items-center gap-2">
        {confirming ? (
          <>
            <Button variant="danger" size="sm" loading={busy} onClick={handleDeactivate}>
              {t('settings.deactivateConfirm')}
            </Button>
            <Button variant="secondary" size="sm" onClick={() => setConfirming(false)}>
              {t('common.cancel')}
            </Button>
          </>
        ) : (
          <Button variant="danger" size="sm" onClick={() => setConfirming(true)}>
            {t('settings.deactivate')}
          </Button>
        )}
      </div>
    </Card>
  );
}

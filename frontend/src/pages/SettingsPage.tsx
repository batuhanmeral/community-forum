import { useEffect, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { AxiosError } from 'axios';
import { resendVerificationEmail } from '@/api/auth';
import { changePassword, deleteAccount, downloadAccountExport, updatePreferences } from '@/api/users';
import { withAuthLock } from '@/api/client';
import { listBlocked, unblockUser, type FollowUser } from '@/api/follow';
import { logout, setAccessToken, setUser } from '@/features/auth/authSlice';
import { useAppDispatch, useAppSelector } from '@/app/hooks';
import { Avatar } from '@/components/ui/Avatar';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { PageTitle } from '@/components/ui/PageTitle';
import { cn } from '@/lib/cn';
import { LANGUAGES, type Language } from '@/i18n';
import { readThemeChoice, setThemeChoice, type ThemeChoice } from '@/lib/theme';

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
      <DataExportCard />
      <DangerZoneCard />
    </div>
  );
}

function PreferencesCard() {
  const { t, i18n } = useTranslation();
  const user = useAppSelector((s) => s.auth.user);
  const dispatch = useAppDispatch();
  const [busy, setBusy] = useState(false);
  const [theme, setTheme] = useState<ThemeChoice>(readThemeChoice);
  const showNsfw = user?.show_nsfw ?? false;

  function changeTheme(choice: ThemeChoice) {
    setThemeChoice(choice);
    setTheme(choice);
  }

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
          className="h-9 rounded-[var(--radius-control)] border border-[var(--color-border)] bg-[var(--color-bg-3)] px-3 text-sm text-[var(--color-text)] focus:border-[var(--color-link)] focus:outline-none"
        >
          {LANGUAGES.map((l) => (
            <option key={l.code} value={l.code}>
              {l.label}
            </option>
          ))}
        </select>
      </label>
      <label className="mt-2.5 flex items-center justify-between gap-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-2.5">
        <span className="text-sm">
          <span className="font-medium">{t('settings.theme')}</span>
          <span className="ml-2 text-[var(--color-text-muted)]">{t('settings.themeHint')}</span>
        </span>
        <select
          value={theme}
          onChange={(e) => changeTheme(e.target.value as ThemeChoice)}
          className="h-9 rounded-[var(--radius-control)] border border-[var(--color-border)] bg-[var(--color-bg-3)] px-3 text-sm text-[var(--color-text)] focus:border-[var(--color-link)] focus:outline-none"
        >
          <option value="system">{t('settings.themeSystem')}</option>
          <option value="light">{t('settings.themeLight')}</option>
          <option value="dark">{t('settings.themeDark')}</option>
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
      dispatch(setAccessToken(tokens.access));
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

function DataExportCard() {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  async function handleDownload() {
    setBusy(true);
    setFailed(false);
    try {
      const blob = await downloadAccountExport();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'nexus-export.json';
      link.click();
      URL.revokeObjectURL(url);
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h2 className="text-base font-semibold tracking-tight">{t('settings.dataTitle')}</h2>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">{t('settings.dataHint')}</p>
      <div className="mt-3">
        <Button variant="secondary" size="sm" loading={busy} onClick={handleDownload}>
          {t('settings.dataDownload')}
        </Button>
      </div>
      {failed && <p className="mt-2 text-sm text-[var(--color-danger)]">{t('settings.dataFailed')}</p>}
    </Card>
  );
}

function DangerZoneCard() {
  const { t } = useTranslation();
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const [confirming, setConfirming] = useState(false);
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleDelete(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      // Outside the lock: the request may itself need a refresh, and the lock is not re-entrant.
      await deleteAccount(password);
      // Under it, so a refresh in flight in another tab can't restore the session just deleted.
      await withAuthLock(async () => {
        dispatch(logout());
      });
      navigate('/', { replace: true });
    } catch (err) {
      const wrongPassword = (err as AxiosError).response?.status === 400;
      setError(t(wrongPassword ? 'settings.deleteWrongPassword' : 'settings.deleteFailed'));
      setBusy(false);
    }
  }

  function cancel() {
    setConfirming(false);
    setPassword('');
    setError(null);
  }

  return (
    <Card>
      <h2 className="text-base font-semibold tracking-tight text-[var(--color-danger)]">
        {t('settings.dangerTitle')}
      </h2>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">{t('settings.dangerHint')}</p>
      {confirming ? (
        <form onSubmit={handleDelete} className="mt-3 flex flex-col gap-3">
          <Input
            name="delete-password"
            type="password"
            autoComplete="current-password"
            label={t('settings.deletePassword')}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={error}
            required
          />
          <div className="flex flex-wrap items-center gap-2">
            <Button type="submit" variant="danger" size="sm" loading={busy} disabled={!password}>
              {t('settings.deleteConfirm')}
            </Button>
            <Button type="button" variant="secondary" size="sm" onClick={cancel}>
              {t('common.cancel')}
            </Button>
          </div>
        </form>
      ) : (
        <div className="mt-3">
          <Button variant="danger" size="sm" onClick={() => setConfirming(true)}>
            {t('settings.deleteAccount')}
          </Button>
        </div>
      )}
    </Card>
  );
}

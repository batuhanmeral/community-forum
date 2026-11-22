import { useEffect, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import {
  confirmMfa,
  disableMfa,
  getMfaStatus,
  regenerateRecoveryCodes,
  startMfaSetup,
  type MfaSessionResult,
  type MfaSetup,
  type MfaStatus,
} from '@/api/users';
import { setAccessToken } from '@/features/auth/authSlice';
import { useAppDispatch } from '@/app/hooks';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';

type Step =
  | { kind: 'idle' }
  | { kind: 'password' }
  | { kind: 'scan'; setup: MfaSetup }
  | { kind: 'codes'; codes: string[] }
  | { kind: 'manage'; action: 'disable' | 'regenerate' };

export function TwoFactorCard() {
  const { t } = useTranslation();
  const dispatch = useAppDispatch();
  const [status, setStatus] = useState<MfaStatus | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [step, setStep] = useState<Step>({ kind: 'idle' });
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMfaStatus()
      .then(setStatus)
      .catch(() => setLoadFailed(true));
  }, []);

  function reset(next: Step = { kind: 'idle' }) {
    setStep(next);
    setPassword('');
    setCode('');
    setError(null);
  }

  /** Enabling, disabling and regenerating end other sessions; keep this one alive. */
  function adopt(result: MfaSessionResult) {
    dispatch(setAccessToken(result.access));
  }

  async function run(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (err) {
      const statusCode = (err as { response?: { status?: number } })?.response?.status;
      setError(
        statusCode === 429
          ? t('settings.mfaLocked')
          : statusCode === 503
            ? t('settings.mfaUnavailable')
            : t('settings.mfaFailed'),
      );
    } finally {
      setBusy(false);
    }
  }

  async function submitPassword(e: FormEvent) {
    e.preventDefault();
    await run(async () => {
      const setup = await startMfaSetup(password);
      reset({ kind: 'scan', setup });
    });
  }

  async function submitCode(e: FormEvent) {
    e.preventDefault();
    await run(async () => {
      const result = await confirmMfa(code.trim());
      adopt(result);
      setStatus({ available: true, enabled: true, recovery_codes_remaining: result.recovery_codes?.length ?? 0 });
      reset({ kind: 'codes', codes: result.recovery_codes ?? [] });
    });
  }

  async function submitManage(e: FormEvent, action: 'disable' | 'regenerate') {
    e.preventDefault();
    await run(async () => {
      if (action === 'disable') {
        adopt(await disableMfa(password, code.trim()));
        setStatus({ available: true, enabled: false, recovery_codes_remaining: 0 });
        reset();
      } else {
        const result = await regenerateRecoveryCodes(password, code.trim());
        adopt(result);
        setStatus({ available: true, enabled: true, recovery_codes_remaining: result.recovery_codes?.length ?? 0 });
        reset({ kind: 'codes', codes: result.recovery_codes ?? [] });
      }
    });
  }

  function downloadCodes(codes: string[]) {
    const blob = new Blob([codes.join('\n') + '\n'], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'nexus-recovery-codes.txt';
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <Card>
      <h2 className="text-base font-semibold tracking-tight">{t('settings.mfaTitle')}</h2>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">{t('settings.mfaHint')}</p>

      {loadFailed ? (
        <p role="alert" className="mt-3 text-sm text-[var(--color-danger)]">
          {t('settings.mfaLoadFailed')}
        </p>
      ) : !status ? (
        <p className="mt-3 text-sm text-[var(--color-text-muted)]">{t('common.loading')}</p>
      ) : !status.available ? (
        <p className="mt-3 text-sm text-[var(--color-text-muted)]">{t('settings.mfaUnavailable')}</p>
      ) : step.kind === 'password' ? (
        <form onSubmit={submitPassword} className="mt-3 flex flex-col gap-3">
          <Input
            name="mfa-password"
            type="password"
            label={t('settings.currentPassword')}
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <div className="flex gap-2">
            <Button type="submit" loading={busy} disabled={!password}>
              {t('settings.mfaContinue')}
            </Button>
            <Button type="button" variant="secondary" onClick={() => reset()}>
              {t('common.cancel')}
            </Button>
          </div>
        </form>
      ) : step.kind === 'scan' ? (
        <form onSubmit={submitCode} className="mt-3 flex flex-col gap-3">
          <p className="text-sm">{t('settings.mfaScan')}</p>
          <img src={step.setup.qr_data_uri} alt={t('settings.mfaQrAlt')} className="h-48 w-48 rounded bg-white p-2" />
          <p className="text-xs text-[var(--color-text-muted)]">
            {t('settings.mfaManualKey')} <code className="font-mono">{step.setup.secret}</code>
          </p>
          <Input
            name="mfa-confirm-code"
            label={t('settings.mfaCode')}
            autoComplete="one-time-code"
            inputMode="numeric"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            required
          />
          <div className="flex gap-2">
            <Button type="submit" loading={busy} disabled={!code.trim()}>
              {t('settings.mfaEnable')}
            </Button>
            <Button type="button" variant="secondary" onClick={() => reset()}>
              {t('common.cancel')}
            </Button>
          </div>
        </form>
      ) : step.kind === 'codes' ? (
        <div className="mt-3 flex flex-col gap-3">
          <p className="text-sm font-medium">{t('settings.mfaCodesTitle')}</p>
          <p className="text-xs text-[var(--color-text-muted)]">{t('settings.mfaCodesHint')}</p>
          <ul className="grid grid-cols-2 gap-1 font-mono text-sm">
            {step.codes.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => downloadCodes(step.codes)}>
              {t('settings.mfaDownload')}
            </Button>
            <Button onClick={() => reset()}>{t('settings.mfaDone')}</Button>
          </div>
        </div>
      ) : step.kind === 'manage' ? (
        <form onSubmit={(e) => submitManage(e, step.action)} className="mt-3 flex flex-col gap-3">
          <Input
            name="mfa-manage-password"
            type="password"
            label={t('settings.currentPassword')}
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <Input
            name="mfa-manage-code"
            label={t('settings.mfaCodeOrRecovery')}
            autoComplete="one-time-code"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            required
          />
          <div className="flex gap-2">
            <Button
              type="submit"
              variant={step.action === 'disable' ? 'danger' : 'primary'}
              loading={busy}
              disabled={!password || !code.trim()}
            >
              {step.action === 'disable' ? t('settings.mfaDisable') : t('settings.mfaRegenerate')}
            </Button>
            <Button type="button" variant="secondary" onClick={() => reset()}>
              {t('common.cancel')}
            </Button>
          </div>
        </form>
      ) : status.enabled ? (
        <div className="mt-3 flex flex-col gap-3">
          <p className="text-sm">
            {t('settings.mfaOn', { count: status.recovery_codes_remaining })}
          </p>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => reset({ kind: 'manage', action: 'regenerate' })}>
              {t('settings.mfaRegenerate')}
            </Button>
            <Button variant="danger" onClick={() => reset({ kind: 'manage', action: 'disable' })}>
              {t('settings.mfaDisable')}
            </Button>
          </div>
        </div>
      ) : (
        <div className="mt-3">
          <Button onClick={() => reset({ kind: 'password' })}>{t('settings.mfaSetUp')}</Button>
        </div>
      )}

      {error && (
        <p role="alert" className="mt-3 text-sm text-[var(--color-danger)]">
          {error}
        </p>
      )}
    </Card>
  );
}

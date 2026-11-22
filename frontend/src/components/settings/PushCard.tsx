import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  getPushPreferences,
  updatePushPreferences,
  type PushGroup,
  type PushPreferences,
} from '@/api/push';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { disablePush, enablePush, getPushState, type PushState } from '@/lib/push';

const GROUPS: PushGroup[] = ['messages', 'replies', 'mentions', 'follows', 'moderation'];

export function PushCard() {
  const { t } = useTranslation();
  const [state, setState] = useState<PushState | null>(null);
  const [prefs, setPrefs] = useState<PushPreferences | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getPushState().then((s) => !cancelled && setState(s));
    getPushPreferences()
      .then((p) => !cancelled && setPrefs(p))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  async function toggle() {
    if (busy || !state) return;
    setBusy(true);
    setError(false);
    try {
      if (state === 'on') {
        await disablePush();
        setState('off');
      } else {
        setState(await enablePush());
      }
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  }

  async function change(patch: Parameters<typeof updatePushPreferences>[0]) {
    setError(false);
    try {
      setPrefs(await updatePushPreferences(patch));
    } catch {
      setError(true);
    }
  }

  return (
    <Card>
      <h2 className="text-base font-semibold tracking-tight">{t('settings.pushTitle')}</h2>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">{t('settings.pushHint')}</p>
      {state === null ? (
        <p className="mt-3 text-sm text-[var(--color-text-muted)]">{t('common.loading')}</p>
      ) : state === 'unsupported' ? (
        <p className="mt-3 text-sm text-[var(--color-text-muted)]">{t('settings.pushUnsupported')}</p>
      ) : state === 'unavailable' ? (
        <p className="mt-3 text-sm text-[var(--color-text-muted)]">{t('settings.pushUnavailable')}</p>
      ) : (
        <div className="mt-3 flex flex-col gap-3">
          {state === 'denied' && (
            <p className="text-sm text-[var(--color-text-muted)]">{t('settings.pushDenied')}</p>
          )}
          <div>
            <Button
              variant={state === 'on' ? 'secondary' : 'primary'}
              loading={busy}
              disabled={state === 'denied'}
              onClick={toggle}
            >
              {state === 'on' ? t('settings.pushDisable') : t('settings.pushEnable')}
            </Button>
          </div>
          {state === 'on' && prefs && (
            <fieldset className="flex flex-col gap-2">
              <legend className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-muted)]">
                {t('settings.pushTypes')}
              </legend>
              {GROUPS.map((group) => (
                <label key={group} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={prefs.types[group]}
                    onChange={(e) => void change({ types: { [group]: e.target.checked } })}
                  />
                  {t(`settings.pushType_${group}`)}
                </label>
              ))}
            </fieldset>
          )}
        </div>
      )}
      {error && (
        <p role="alert" className="mt-3 text-sm text-[var(--color-danger)]">
          {t('settings.pushFailed')}
        </p>
      )}
    </Card>
  );
}

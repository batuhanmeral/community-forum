import { deletePushSubscription, getPushConfig, savePushSubscription } from '@/api/push';

export type PushState = 'unsupported' | 'unavailable' | 'denied' | 'off' | 'on';

export function pushSupported(): boolean {
  return (
    typeof navigator !== 'undefined' &&
    'serviceWorker' in navigator &&
    typeof window !== 'undefined' &&
    'PushManager' in window &&
    'Notification' in window
  );
}

/** Registers the worker in production builds only; the dev server must not cache anything. */
export async function registerServiceWorker(): Promise<void> {
  if (!import.meta.env.PROD || !('serviceWorker' in navigator)) return;
  try {
    await navigator.serviceWorker.register('/sw.js', { scope: '/' });
  } catch {
    // Push and caching are optional; the app works without a worker.
  }
}

// applicationServerKey wants bytes; the server hands out URL-safe base64.
export function urlBase64ToUint8Array(value: string): Uint8Array<ArrayBuffer> {
  const padded = value + '='.repeat((4 - (value.length % 4)) % 4);
  const raw = atob(padded.replace(/-/g, '+').replace(/_/g, '/'));
  const out = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i += 1) out[i] = raw.charCodeAt(i);
  return out;
}

async function currentSubscription(): Promise<PushSubscription | null> {
  const registration = await navigator.serviceWorker.getRegistration();
  return registration ? registration.pushManager.getSubscription() : null;
}

/** Where this browser stands: not possible, not offered by the server, blocked, off or on. */
export async function getPushState(): Promise<PushState> {
  if (!pushSupported()) return 'unsupported';
  try {
    const config = await getPushConfig();
    if (!config.enabled) return 'unavailable';
  } catch {
    return 'unavailable';
  }
  if (Notification.permission === 'denied') return 'denied';
  const subscription = await currentSubscription();
  if (!subscription) return 'off';
  // The server drops subscriptions when sessions are revoked (password or MFA change); the
  // browser keeps its own. Re-registering is idempotent and heals that mismatch.
  try {
    await savePushSubscription(subscription.toJSON());
  } catch {
    // Offline or signed out: the browser still holds the subscription.
  }
  return 'on';
}

/** Asks for permission, subscribes this browser and tells the server. */
export async function enablePush(): Promise<PushState> {
  if (!pushSupported()) return 'unsupported';
  const config = await getPushConfig();
  if (!config.enabled) return 'unavailable';
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') return permission === 'denied' ? 'denied' : 'off';
  const registration = await navigator.serviceWorker.ready;
  const subscription =
    (await registration.pushManager.getSubscription()) ??
    (await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(config.public_key),
    }));
  await savePushSubscription(subscription.toJSON());
  return 'on';
}

/** Unsubscribes this browser and removes it on the server. */
export async function disablePush(): Promise<void> {
  const subscription = await currentSubscription();
  if (!subscription) return;
  const { endpoint } = subscription;
  await subscription.unsubscribe();
  await deletePushSubscription(endpoint);
}

/** Best effort before logout: never blocks or fails the logout. */
export async function removePushOnLogout(): Promise<void> {
  try {
    if (pushSupported()) await disablePush();
  } catch {
    // The server also drops subscriptions when sessions are revoked.
  }
}

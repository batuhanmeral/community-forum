import { beforeEach, describe, expect, it, vi } from 'vitest';
import { disablePush, enablePush, getPushState, removePushOnLogout, urlBase64ToUint8Array } from './push';
import * as api from '@/api/push';

vi.mock('@/api/push');

function fakeBrowser(options: { permission?: NotificationPermission; subscribed?: boolean } = {}) {
  const subscription = {
    endpoint: 'https://fcm.googleapis.com/fcm/send/abc',
    toJSON: () => ({ endpoint: 'https://fcm.googleapis.com/fcm/send/abc', keys: { p256dh: 'p', auth: 'a' } }),
    unsubscribe: vi.fn(async () => true),
  };
  const pushManager = {
    getSubscription: vi.fn(async () => (options.subscribed ? subscription : null)),
    subscribe: vi.fn(async () => subscription),
  };
  const registration = { pushManager };
  vi.stubGlobal('PushManager', class {});
  vi.stubGlobal('Notification', {
    permission: options.permission ?? 'default',
    requestPermission: vi.fn(async () => options.permission ?? 'granted'),
  });
  Object.defineProperty(navigator, 'serviceWorker', {
    configurable: true,
    value: { ready: Promise.resolve(registration), getRegistration: vi.fn(async () => registration) },
  });
  return { subscription, pushManager };
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.getPushConfig).mockResolvedValue({ enabled: true, public_key: 'BEl6' });
});

describe('push state resync', () => {
  it('re-registers an existing browser subscription with the server (it may have been dropped)', async () => {
    fakeBrowser({ subscribed: true });
    expect(await getPushState()).toBe('on');
    expect(api.savePushSubscription).toHaveBeenCalledWith(
      expect.objectContaining({ endpoint: 'https://fcm.googleapis.com/fcm/send/abc' }),
    );
  });

  it('still reports on when the resync request fails (offline)', async () => {
    fakeBrowser({ subscribed: true });
    vi.mocked(api.savePushSubscription).mockRejectedValue(new Error('offline'));
    expect(await getPushState()).toBe('on');
  });

  it('does not resync when there is no subscription', async () => {
    fakeBrowser();
    expect(await getPushState()).toBe('off');
    expect(api.savePushSubscription).not.toHaveBeenCalled();
  });
});

describe('push helpers', () => {
  it('decodes url-safe base64 for applicationServerKey', () => {
    expect(Array.from(urlBase64ToUint8Array('AQID'))).toEqual([1, 2, 3]);
    expect(Array.from(urlBase64ToUint8Array('-_8'))).toEqual([251, 255]);
  });

  it('reports each state', async () => {
    fakeBrowser();
    expect(await getPushState()).toBe('off');
    fakeBrowser({ subscribed: true });
    expect(await getPushState()).toBe('on');
    fakeBrowser({ permission: 'denied' });
    expect(await getPushState()).toBe('denied');
    vi.mocked(api.getPushConfig).mockResolvedValue({ enabled: false, public_key: '' });
    expect(await getPushState()).toBe('unavailable');
  });

  it('reports an unsupported browser', async () => {
    vi.stubGlobal('PushManager', undefined);
    delete (window as { PushManager?: unknown }).PushManager;
    expect(await getPushState()).toBe('unsupported');
  });

  it('subscribes with the server key after permission is granted and saves it', async () => {
    const { pushManager } = fakeBrowser();
    expect(await enablePush()).toBe('on');
    expect(pushManager.subscribe).toHaveBeenCalledWith(
      expect.objectContaining({ userVisibleOnly: true }),
    );
    expect(api.savePushSubscription).toHaveBeenCalledWith(
      expect.objectContaining({ endpoint: 'https://fcm.googleapis.com/fcm/send/abc' }),
    );
  });

  it('does not subscribe when permission is refused', async () => {
    const { pushManager } = fakeBrowser({ permission: 'denied' });
    expect(await enablePush()).toBe('denied');
    expect(pushManager.subscribe).not.toHaveBeenCalled();
    expect(api.savePushSubscription).not.toHaveBeenCalled();
  });

  it('unsubscribes locally and on the server', async () => {
    const { subscription } = fakeBrowser({ subscribed: true });
    await disablePush();
    expect(subscription.unsubscribe).toHaveBeenCalled();
    expect(api.deletePushSubscription).toHaveBeenCalledWith('https://fcm.googleapis.com/fcm/send/abc');
  });

  it('never lets a push cleanup failure break logout', async () => {
    fakeBrowser({ subscribed: true });
    vi.mocked(api.deletePushSubscription).mockRejectedValue(new Error('offline'));
    await expect(removePushOnLogout()).resolves.toBeUndefined();
  });
});

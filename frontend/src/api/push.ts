import { api } from './client';

export interface PushConfig {
  enabled: boolean;
  public_key: string;
}

export type PushGroup = 'messages' | 'replies' | 'mentions' | 'follows' | 'moderation';

export interface PushPreferences {
  enabled: boolean;
  types: Record<PushGroup, boolean>;
}

export async function getPushConfig(): Promise<PushConfig> {
  const res = await api.get<PushConfig>('/push/config/');
  return res.data;
}

/** `subscription` is the browser's `PushSubscription.toJSON()`. */
export async function savePushSubscription(subscription: PushSubscriptionJSON): Promise<void> {
  await api.post('/push/subscriptions/', {
    endpoint: subscription.endpoint,
    keys: subscription.keys,
  });
}

export async function deletePushSubscription(endpoint: string): Promise<void> {
  await api.delete('/push/subscriptions/', { data: { endpoint } });
}

export async function getPushPreferences(): Promise<PushPreferences> {
  const res = await api.get<PushPreferences>('/push/preferences/');
  return res.data;
}

export async function updatePushPreferences(
  patch: { enabled?: boolean; types?: Partial<Record<PushGroup, boolean>> },
): Promise<PushPreferences> {
  const res = await api.put<PushPreferences>('/push/preferences/', patch);
  return res.data;
}

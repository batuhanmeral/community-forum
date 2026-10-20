import type { AppDispatch } from '@/app/store';
import { getUnreadCounts } from '@/api/users';
import { setDMUnreadCount } from '@/features/messaging/messagingSlice';
import { setUnreadCount } from './notificationSlice';

/** The one place that fetches both nav badge counts; a failed request keeps the last values. */
export async function syncUnreadCounts(dispatch: AppDispatch): Promise<void> {
  let counts;
  try {
    counts = await getUnreadCounts();
  } catch {
    return;
  }
  dispatch(setUnreadCount(counts.notifications));
  dispatch(setDMUnreadCount(counts.messages));
}

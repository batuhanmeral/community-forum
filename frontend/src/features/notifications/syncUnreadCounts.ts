import type { AppDispatch, RootState } from '@/app/store';
import { getUnreadCounts } from '@/api/users';
import { setDMUnreadCount } from '@/features/messaging/messagingSlice';
import { setUnreadCount } from './notificationSlice';

/** The one place that fetches both nav badge counts; a failed request keeps the last values. */
export async function syncUnreadCounts(
  dispatch: AppDispatch,
  getState: () => RootState,
): Promise<void> {
  let counts;
  try {
    counts = await getUnreadCounts();
  } catch {
    return;
  }
  // The user may have logged out while the request was in flight; those counts are not theirs any more.
  if (getState().auth.status !== 'authenticated') return;
  dispatch(setUnreadCount(counts.notifications));
  dispatch(setDMUnreadCount(counts.messages));
}

import type { AppStore } from '@/app/store';
import { SESSION_KEY, logout, readSessionUserId, sessionChanged } from './authSlice';

/** Mirrors login, logout and account switches done in other tabs into this tab's store. */
export function startAuthStorageSync(store: AppStore): () => void {
  const onStorage = (event: StorageEvent) => {
    // A null key means another tab called localStorage.clear().
    if (event.key !== SESSION_KEY && event.key !== null) return;
    const userId = readSessionUserId();
    if (!userId) store.dispatch(logout());
    else if (userId !== store.getState().auth.sessionUserId) store.dispatch(sessionChanged(userId));
  };
  window.addEventListener('storage', onStorage);
  return () => window.removeEventListener('storage', onStorage);
}

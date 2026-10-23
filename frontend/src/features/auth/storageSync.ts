import type { AppStore } from '@/app/store';
import { REFRESH_KEY, logout, readStoredTokens, syncFromStorage } from './authSlice';

/** Mirrors login, logout and token rotation done in other tabs into this tab's store. */
export function startAuthStorageSync(store: AppStore): () => void {
  const onStorage = (event: StorageEvent) => {
    // A null key means another tab called localStorage.clear().
    if (event.key !== REFRESH_KEY && event.key !== null) return;
    // setTokens writes the access token first, so both are in storage by the time this fires.
    const { access, refresh } = readStoredTokens();
    if (!refresh) store.dispatch(logout());
    else if (access) store.dispatch(syncFromStorage({ access, refresh }));
  };
  window.addEventListener('storage', onStorage);
  return () => window.removeEventListener('storage', onStorage);
}

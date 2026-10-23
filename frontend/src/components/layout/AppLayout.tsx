import { useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { useStore } from 'react-redux';
import { useAppDispatch, useAppSelector } from '@/app/hooks';
import type { RootState } from '@/app/store';
import { fetchMe } from '@/api/auth';
import { setUser } from '@/features/auth/authSlice';
import { Navbar } from './Navbar';
import { Sidebar } from './Sidebar';
import { HomeRightSidebar } from './HomeRightSidebar';
import { MobileNav } from './MobileNav';
import { cn } from '@/lib/cn';

const PROFILE_RETRY_MS = 30_000;

export function AppLayout() {
  const dispatch = useAppDispatch();
  const { getState } = useStore<RootState>();
  const { sessionUserId, user } = useAppSelector((s) => s.auth);
  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);
  const [menuOpen, setMenuOpen] = useState(false);
  const { key: locationKey } = useLocation();

  // Any navigation closes the drawer, including ones started outside it (back button, links in the page).
  useEffect(() => {
    setMenuOpen(false);
  }, [locationKey]);

  useEffect(() => {
    if (!sessionUserId || user) return;
    let active = true;
    let lastAttempt = 0;
    const load = () => {
      lastAttempt = Date.now();
      return fetchMe().then((u) => {
        // A logout or account switch (possibly in another tab) while loading makes this user stale.
        if (active && getState().auth.sessionUserId === String(u.id)) dispatch(setUser(u));
      });
    };
    const retry = () => void load().catch(() => undefined);
    // Returning to the tab also retries (5xx, transient refresh failure), at most once per PROFILE_RETRY_MS.
    const retryWhenBack = () => {
      if (!document.hidden && Date.now() - lastAttempt >= PROFILE_RETRY_MS) retry();
    };
    // Logout belongs to the refresh path; a failed load (often offline) retries once on reconnect.
    load().catch(() => {
      if (!active) return;
      window.addEventListener('online', retry, { once: true });
      window.addEventListener('focus', retryWhenBack);
      document.addEventListener('visibilitychange', retryWhenBack);
    });
    return () => {
      active = false;
      window.removeEventListener('online', retry);
      window.removeEventListener('focus', retryWhenBack);
      document.removeEventListener('visibilitychange', retryWhenBack);
    };
  }, [sessionUserId, user, dispatch, getState]);

  return (
    <div className="min-h-screen text-[var(--color-text)]">
      <Navbar
        leftOpen={leftOpen}
        rightOpen={rightOpen}
        onToggleLeft={() => setLeftOpen((o) => !o)}
        onToggleRight={() => setRightOpen((o) => !o)}
        onOpenMenu={() => setMenuOpen(true)}
      />
      <MobileNav open={menuOpen} onClose={() => setMenuOpen(false)} />
      <div className="relative mx-auto flex max-w-[1280px] gap-5 px-20 pb-20 max-[1180px]:px-10 max-[960px]:px-4">
        {/* Left sidebar */}
        <div
          className={cn(
            'shrink-0 transition-all duration-300 ease-in-out max-[960px]:hidden',
            leftOpen ? 'w-[200px] opacity-100 max-[1180px]:w-[170px]' : 'w-0 overflow-hidden opacity-0',
          )}
        >
          <Sidebar />
        </div>

        {/* Main content */}
        <main className="min-w-0 flex-1 pt-6">
          <Outlet />
        </main>

        {/* Right sidebar */}
        <div
          className={cn(
            'shrink-0 transition-all duration-300 ease-in-out max-[960px]:hidden',
            rightOpen ? 'w-[300px] opacity-100 max-[1180px]:w-[260px]' : 'w-0 overflow-hidden opacity-0',
          )}
        >
          <HomeRightSidebar />
        </div>
      </div>
    </div>
  );
}

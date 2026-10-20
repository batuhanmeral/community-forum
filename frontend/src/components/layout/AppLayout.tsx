import { useEffect, useState } from 'react';
import { Outlet } from 'react-router-dom';
import { useStore } from 'react-redux';
import { useAppDispatch, useAppSelector } from '@/app/hooks';
import type { RootState } from '@/app/store';
import { fetchMe } from '@/api/auth';
import { setUser } from '@/features/auth/authSlice';
import { jwtUserId } from '@/features/auth/jwt';
import { Navbar } from './Navbar';
import { Sidebar } from './Sidebar';
import { HomeRightSidebar } from './HomeRightSidebar';
import { cn } from '@/lib/cn';

export function AppLayout() {
  const dispatch = useAppDispatch();
  const { getState } = useStore<RootState>();
  const { accessToken, user } = useAppSelector((s) => s.auth);
  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);

  useEffect(() => {
    if (!accessToken || user) return;
    let active = true;
    const load = () =>
      fetchMe().then((u) => {
        // A logout or account switch (possibly in another tab) while loading makes this user stale.
        const current = getState().auth.accessToken;
        if (active && current && jwtUserId(current) === String(u.id)) dispatch(setUser(u));
      });
    const retry = () => void load().catch(() => undefined);
    // Logout belongs to the refresh path; a failed load (often offline) retries once on reconnect.
    load().catch(() => {
      if (active) window.addEventListener('online', retry, { once: true });
    });
    return () => {
      active = false;
      window.removeEventListener('online', retry);
    };
  }, [accessToken, user, dispatch, getState]);

  return (
    <div className="min-h-screen text-[var(--color-text)]">
      <Navbar
        leftOpen={leftOpen}
        rightOpen={rightOpen}
        onToggleLeft={() => setLeftOpen((o) => !o)}
        onToggleRight={() => setRightOpen((o) => !o)}
      />
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

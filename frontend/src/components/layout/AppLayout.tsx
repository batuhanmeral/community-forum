import { useEffect, useState } from 'react';
import { Outlet } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from '@/app/hooks';
import { fetchMe } from '@/api/auth';
import { logout, setUser } from '@/features/auth/authSlice';
import { Navbar } from './Navbar';
import { Sidebar } from './Sidebar';
import { HomeRightSidebar } from './HomeRightSidebar';
import { cn } from '@/lib/cn';

export function AppLayout() {
  const dispatch = useAppDispatch();
  const { accessToken, user } = useAppSelector((s) => s.auth);
  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);

  useEffect(() => {
    if (accessToken && !user) {
      fetchMe()
        .then((u) => dispatch(setUser(u)))
        .catch(() => dispatch(logout()));
    }
  }, [accessToken, user, dispatch]);

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

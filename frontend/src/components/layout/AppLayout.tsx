import { useEffect } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from '@/app/hooks';
import { fetchMe } from '@/api/auth';
import { logout, setUser } from '@/features/auth/authSlice';
import { Navbar } from './Navbar';
import { Sidebar } from './Sidebar';
import { HomeRightSidebar } from './HomeRightSidebar';

export function AppLayout() {
  const dispatch = useAppDispatch();
  const location = useLocation();
  const { accessToken, user } = useAppSelector((s) => s.auth);

  const isHome = location.pathname === '/' || location.pathname === '/popular' || location.pathname === '/all' || location.pathname === '/explore';

  useEffect(() => {
    if (accessToken && !user) {
      fetchMe()
        .then((u) => dispatch(setUser(u)))
        .catch(() => dispatch(logout()));
    }
  }, [accessToken, user, dispatch]);

  return (
    <div className="min-h-screen text-[var(--color-text)]">
      <Navbar />
      <div
        className={
          isHome
            ? 'mx-auto grid max-w-[1480px] grid-cols-[280px_minmax(0,1fr)_340px] gap-7 px-8 pb-20 max-[1180px]:grid-cols-[240px_minmax(0,1fr)_300px] max-[1180px]:gap-5 max-[1180px]:px-5 max-[960px]:grid-cols-[minmax(0,1fr)] max-[960px]:px-4'
            : 'mx-auto flex max-w-[1240px] gap-6 px-4 py-6 sm:px-6 lg:px-12 xl:px-16'
        }
      >
        <Sidebar />
        <main className="min-w-0 flex-1 pt-6">
          <Outlet />
        </main>
        {isHome && <HomeRightSidebar />}
      </div>
    </div>
  );
}

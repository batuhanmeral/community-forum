import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAppSelector } from '@/app/hooks';

export function ProtectedRoute() {
  const location = useLocation();
  const sessionUserId = useAppSelector((s) => s.auth.sessionUserId);

  if (!sessionUserId) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  // A different account (switched in another tab) gets a fresh page instead of the previous account's state.
  return <Outlet key={sessionUserId} />;
}

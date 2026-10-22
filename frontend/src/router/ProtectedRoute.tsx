import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAppSelector } from '@/app/hooks';
import { jwtUserId } from '@/features/auth/jwt';

export function ProtectedRoute() {
  const location = useLocation();
  const accessToken = useAppSelector((s) => s.auth.accessToken);

  if (!accessToken) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  // A different account (switched in another tab) gets a fresh page instead of the previous account's state.
  return <Outlet key={jwtUserId(accessToken) ?? undefined} />;
}

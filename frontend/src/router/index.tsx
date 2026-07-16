import { createBrowserRouter } from 'react-router-dom';
import { AppLayout } from '@/components/layout/AppLayout';
import { HomePage } from '@/pages/HomePage';
import { LoginPage } from '@/pages/LoginPage';
import { RegisterPage } from '@/pages/RegisterPage';
import { NotFoundPage } from '@/pages/NotFoundPage';
import { ProtectedRoute } from './ProtectedRoute';

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/register', element: <RegisterPage /> },
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'popular', element: <HomePage /> },
      { path: 'explore', element: <HomePage /> },
      { path: 'all', element: <HomePage /> },
      {
        element: <ProtectedRoute />,
        children: [
          { path: 'settings', element: <div className="p-4">Settings (coming soon)</div> },
        ],
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);

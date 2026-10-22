import { Suspense } from 'react';
import type { ReactNode } from 'react';
import { createBrowserRouter, type RouteObject } from 'react-router-dom';
import { AppLayout } from '@/components/layout/AppLayout';
import { ProtectedRoute } from './ProtectedRoute';
import { RouteErrorPage } from './RouteErrorPage';
import { PageTitle } from '@/components/ui/PageTitle';
import {
  CommunityCreatePage,
  ForgotPasswordPage,
  CommunityDetailPage,
  CommunityListPage,
  HomePage,
  InboxPage,
  LoginPage,
  MessagesPage,
  ModPage,
  NotFoundPage,
  PostCreatePage,
  PostDetailPage,
  RegisterPage,
  ResetPasswordPage,
  SavedPage,
  SearchPage,
  SettingsPage,
  UserProfilePage,
  VerifyEmailPage,
} from './pages';

function page(node: ReactNode) {
  return (
    <Suspense
      fallback={
        <div className="flex justify-center py-16">
          <PageTitle />
          <span className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-current border-t-transparent opacity-50" />
        </div>
      }
    >
      {node}
    </Suspense>
  );
}

const errorElement = <RouteErrorPage />;

export const routes: RouteObject[] = [
  { path: '/login', element: page(<LoginPage />), errorElement },
  { path: '/register', element: page(<RegisterPage />), errorElement },
  { path: '/forgot-password', element: page(<ForgotPasswordPage />), errorElement },
  { path: '/reset-password', element: page(<ResetPasswordPage />), errorElement },
  { path: '/verify-email', element: page(<VerifyEmailPage />), errorElement },
  {
    path: '/',
    element: <AppLayout />,
    errorElement,
    children: [
      {
        errorElement,
        children: [
          { index: true, element: page(<HomePage />) },
          { path: 'popular', element: page(<HomePage variant="popular" />) },
          { path: 'all', element: page(<HomePage variant="all" />) },
          { path: 'c', element: page(<CommunityListPage />) },
          { path: 'c/:slug', element: page(<CommunityDetailPage />) },
          { path: 'posts/:id', element: page(<PostDetailPage />) },
          { path: 'u/:username', element: page(<UserProfilePage />) },
          { path: 'search', element: page(<SearchPage />) },
          {
            element: <ProtectedRoute />,
            children: [
              { path: 'c/create', element: page(<CommunityCreatePage />) },
              { path: 'c/:slug/mod', element: page(<ModPage />) },
              { path: 'submit', element: page(<PostCreatePage />) },
              { path: 'c/:slug/submit', element: page(<PostCreatePage />) },
              { path: 'messages', element: page(<MessagesPage />) },
              { path: 'messages/:id', element: page(<MessagesPage />) },
              { path: 'inbox', element: page(<InboxPage />) },
              { path: 'saved', element: page(<SavedPage />) },
              { path: 'settings', element: page(<SettingsPage />) },
            ],
          },
          { path: '*', element: page(<NotFoundPage />) },
        ],
      },
    ],
  },
];

export const router = createBrowserRouter(routes);

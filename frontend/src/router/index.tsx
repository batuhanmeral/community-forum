import { Suspense } from 'react';
import type { ReactNode } from 'react';
import { createBrowserRouter } from 'react-router-dom';
import { AppLayout } from '@/components/layout/AppLayout';
import { ProtectedRoute } from './ProtectedRoute';
import {
  CommunityCreatePage,
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
  SavedPage,
  SearchPage,
  SettingsPage,
  UserProfilePage,
} from './pages';

function page(node: ReactNode) {
  return (
    <Suspense
      fallback={
        <div className="flex justify-center py-16">
          <span className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-current border-t-transparent opacity-50" />
        </div>
      }
    >
      {node}
    </Suspense>
  );
}

export const router = createBrowserRouter([
  { path: '/login', element: page(<LoginPage />) },
  { path: '/register', element: page(<RegisterPage />) },
  {
    path: '/',
    element: <AppLayout />,
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
]);

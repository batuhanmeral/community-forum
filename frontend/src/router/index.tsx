import { createBrowserRouter } from 'react-router-dom';
import { AppLayout } from '@/components/layout/AppLayout';
import { HomePage } from '@/pages/HomePage';
import { LoginPage } from '@/pages/LoginPage';
import { RegisterPage } from '@/pages/RegisterPage';
import { NotFoundPage } from '@/pages/NotFoundPage';
import { CommunityListPage } from '@/pages/CommunityListPage';
import { CommunityCreatePage } from '@/pages/CommunityCreatePage';
import { CommunityDetailPage } from '@/pages/CommunityDetailPage';
import { PostCreatePage } from '@/pages/PostCreatePage';
import { PostDetailPage } from '@/pages/PostDetailPage';
import { UserProfilePage } from '@/pages/UserProfilePage';
import { MessagesPage } from '@/pages/MessagesPage';
import { InboxPage } from '@/pages/InboxPage';
import { SavedPage } from '@/pages/SavedPage';
import { SearchPage } from '@/pages/SearchPage';
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
      { path: 'c', element: <CommunityListPage /> },
      { path: 'c/:slug', element: <CommunityDetailPage /> },
      { path: 'posts/:id', element: <PostDetailPage /> },
      { path: 'u/:username', element: <UserProfilePage /> },
      { path: 'search', element: <SearchPage /> },
      {
        element: <ProtectedRoute />,
        children: [
          { path: 'c/create', element: <CommunityCreatePage /> },
          { path: 'submit', element: <PostCreatePage /> },
          { path: 'c/:slug/submit', element: <PostCreatePage /> },
          { path: 'messages', element: <MessagesPage /> },
          { path: 'messages/:id', element: <MessagesPage /> },
          { path: 'inbox', element: <InboxPage /> },
          { path: 'saved', element: <SavedPage /> },
          { path: 'settings', element: <div className="p-4">Settings (coming soon)</div> },
        ],
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);

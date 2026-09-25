import { lazy } from 'react';

// Route-level code splitting: her sayfa ayrı chunk olarak yüklenir.
export const HomePage = lazy(() =>
  import('@/pages/HomePage').then((m) => ({ default: m.HomePage })),
);
export const LoginPage = lazy(() =>
  import('@/pages/LoginPage').then((m) => ({ default: m.LoginPage })),
);
export const RegisterPage = lazy(() =>
  import('@/pages/RegisterPage').then((m) => ({ default: m.RegisterPage })),
);
export const NotFoundPage = lazy(() =>
  import('@/pages/NotFoundPage').then((m) => ({ default: m.NotFoundPage })),
);
export const CommunityListPage = lazy(() =>
  import('@/pages/CommunityListPage').then((m) => ({ default: m.CommunityListPage })),
);
export const CommunityCreatePage = lazy(() =>
  import('@/pages/CommunityCreatePage').then((m) => ({ default: m.CommunityCreatePage })),
);
export const CommunityDetailPage = lazy(() =>
  import('@/pages/CommunityDetailPage').then((m) => ({ default: m.CommunityDetailPage })),
);
export const PostCreatePage = lazy(() =>
  import('@/pages/PostCreatePage').then((m) => ({ default: m.PostCreatePage })),
);
export const PostDetailPage = lazy(() =>
  import('@/pages/PostDetailPage').then((m) => ({ default: m.PostDetailPage })),
);
export const UserProfilePage = lazy(() =>
  import('@/pages/UserProfilePage').then((m) => ({ default: m.UserProfilePage })),
);
export const MessagesPage = lazy(() =>
  import('@/pages/MessagesPage').then((m) => ({ default: m.MessagesPage })),
);
export const InboxPage = lazy(() =>
  import('@/pages/InboxPage').then((m) => ({ default: m.InboxPage })),
);
export const SavedPage = lazy(() =>
  import('@/pages/SavedPage').then((m) => ({ default: m.SavedPage })),
);
export const SearchPage = lazy(() =>
  import('@/pages/SearchPage').then((m) => ({ default: m.SearchPage })),
);
export const SettingsPage = lazy(() =>
  import('@/pages/SettingsPage').then((m) => ({ default: m.SettingsPage })),
);
export const ModPage = lazy(() => import('@/pages/ModPage').then((m) => ({ default: m.ModPage })));
export const ForgotPasswordPage = lazy(() =>
  import('@/pages/ForgotPasswordPage').then((m) => ({ default: m.ForgotPasswordPage })),
);
export const ResetPasswordPage = lazy(() =>
  import('@/pages/ResetPasswordPage').then((m) => ({ default: m.ResetPasswordPage })),
);
export const VerifyEmailPage = lazy(() =>
  import('@/pages/VerifyEmailPage').then((m) => ({ default: m.VerifyEmailPage })),
);

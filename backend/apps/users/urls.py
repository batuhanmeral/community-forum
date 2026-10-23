from django.urls import path

from .views import (
    AccountExportView,
    ChangePasswordView,
    EmailVerifyView,
    LeaderboardView,
    LoginView,
    LogoutView,
    MeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RefreshView,
    RegisterView,
    ResendVerificationView,
    UnreadCountsView,
    UserProfileView,
)

auth_urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("password-reset/", PasswordResetRequestView.as_view(), name="auth-password-reset"),
    path(
        "password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="auth-password-reset-confirm",
    ),
    path("verify-email/", EmailVerifyView.as_view(), name="auth-verify-email"),
    path(
        "verify-email/resend/",
        ResendVerificationView.as_view(),
        name="auth-verify-email-resend",
    ),
]

users_urlpatterns = [
    path("me/", MeView.as_view(), name="users-me"),
    path("me/password/", ChangePasswordView.as_view(), name="users-change-password"),
    path("me/export/", AccountExportView.as_view(), name="users-export"),
    path("me/unread-counts/", UnreadCountsView.as_view(), name="users-unread-counts"),
    path("leaderboard/", LeaderboardView.as_view(), name="users-leaderboard"),
    path("<str:username>/", UserProfileView.as_view(), name="users-profile"),
]

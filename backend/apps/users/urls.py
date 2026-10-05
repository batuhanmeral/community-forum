from django.urls import path
from rest_framework_simplejwt.views import TokenBlacklistView

from .views import (
    ChangePasswordView,
    EmailVerifyView,
    LeaderboardView,
    LoginView,
    MeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RefreshView,
    RegisterView,
    ResendVerificationView,
    UserProfileView,
)

auth_urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("logout/", TokenBlacklistView.as_view(), name="auth-logout"),
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
    path("leaderboard/", LeaderboardView.as_view(), name="users-leaderboard"),
    path("<str:username>/", UserProfileView.as_view(), name="users-profile"),
]

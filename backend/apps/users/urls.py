from django.urls import path
from rest_framework_simplejwt.views import (
    TokenBlacklistView,
    TokenObtainPairView,
    TokenRefreshView,
)

from .views import (
    ChangePasswordView,
    LeaderboardView,
    MeView,
    RegisterView,
    UserProfileView,
)

auth_urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("login/", TokenObtainPairView.as_view(), name="auth-login"),
    path("refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("logout/", TokenBlacklistView.as_view(), name="auth-logout"),
]

users_urlpatterns = [
    path("me/", MeView.as_view(), name="users-me"),
    path("me/password/", ChangePasswordView.as_view(), name="users-change-password"),
    path("leaderboard/", LeaderboardView.as_view(), name="users-leaderboard"),
    path("<str:username>/", UserProfileView.as_view(), name="users-profile"),
]

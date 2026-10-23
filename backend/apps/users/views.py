from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotAuthenticated, ValidationError
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.messaging.services import unread_message_count
from apps.notifications.services import unread_notification_count
from apps.social.services import with_social_annotations

from .auth_cookie import clear_refresh_cookie, refresh_from_cookie, with_refresh_cookie
from .emails import send_password_reset_email, send_verification_email
from .serializers import (
    AccountDeleteSerializer,
    ChangePasswordSerializer,
    EmailVerifySerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PublicUserSerializer,
    RegisterSerializer,
    RevocationAwareTokenRefreshSerializer,
    UserSerializer,
)
from .services import delete_account, delete_file_on_commit, export_account

User = get_user_model()


class LoginView(TokenObtainPairView):
    throttle_scope = "auth"
    # JSON only: a cross-site HTML form can't send it, so no other site can plant its session cookie here.
    parser_classes = (JSONParser,)

    def post(self, request, *args, **kwargs):
        return with_refresh_cookie(super().post(request, *args, **kwargs))


class RefreshView(TokenRefreshView):
    serializer_class = RevocationAwareTokenRefreshSerializer
    # Own bucket so failed logins on a shared IP cannot 429 everyone's refresh.
    throttle_scope = "refresh"

    def post(self, request, *args, **kwargs):
        token = refresh_from_cookie(request)
        if not token:
            raise InvalidToken("No refresh cookie.")
        serializer = self.get_serializer(data={"refresh": token})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            raise InvalidToken(exc.args[0]) from exc
        return with_refresh_cookie(Response(serializer.validated_data))


class LogoutView(APIView):
    permission_classes = (permissions.AllowAny,)
    # An expired access token must not stand in the way of ending the session.
    authentication_classes = ()
    # A throttled logout would leave a live cookie behind; the request is cheap.
    throttle_classes = ()

    def post(self, request):
        response = Response(status=status.HTTP_204_NO_CONTENT)
        token = refresh_from_cookie(request)
        # A cross-site POST never carries the Strict cookie, so only a same-site caller can clear it.
        if not token:
            return response
        try:
            RefreshToken(token).blacklist()
        except TokenError:
            pass  # Already dead; the cookie is cleared below either way.
        return clear_refresh_cookie(response)


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = (permissions.AllowAny,)
    throttle_scope = "auth"

    def perform_create(self, serializer):
        user = serializer.save()
        send_verification_email(user)


class MeView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = UserSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self):
        return self.request.user

    def get_throttles(self):
        # Email changes trigger a verification mail, so cap them like auth flows.
        if self.request.method in ("PATCH", "PUT") and "email" in self.request.data:
            self.throttle_scope = "auth"
        # Deletion checks the password, so it is capped like a login.
        if self.request.method == "DELETE":
            self.throttle_scope = "auth"
        return super().get_throttles()

    def perform_update(self, serializer):
        with transaction.atomic():
            # Save onto the locked row: the user loaded at authentication may predate a password
            # change, a karma update or a deletion, and a full save would write those back.
            locked = User.objects.select_for_update().get(pk=serializer.instance.pk)
            if not locked.is_active:
                raise NotAuthenticated()
            serializer.instance = locked
            old_avatar = serializer.instance.avatar
            self._save_profile(serializer)
            # Replaced photos would stay publicly reachable under /media/ unless removed.
            if serializer.instance.avatar.name != old_avatar.name:
                delete_file_on_commit(old_avatar)

    def _save_profile(self, serializer):
        new_email = serializer.validated_data.get("email")
        email_changed = (
            new_email is not None and new_email.lower() != serializer.instance.email.lower()
        )
        extra = {"email_verified": False} if email_changed else {}
        try:
            user = serializer.save(**extra)
        except IntegrityError as exc:
            # Lost a race against the case-insensitive unique constraint.
            raise ValidationError({"email": "This email is already taken."}) from exc
        if email_changed:
            send_verification_email(user)

    def destroy(self, request, *args, **kwargs):
        serializer = AccountDeleteSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        delete_account(request.user)
        return clear_refresh_cookie(Response(status=status.HTTP_204_NO_CONTENT))


class AccountExportView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    throttle_scope = "auth"

    def get(self, request):
        response = JsonResponse(export_account(request.user), json_dumps_params={"indent": 2})
        response["Content-Disposition"] = 'attachment; filename="nexus-export.json"'
        return response


class UnreadCountsView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        return Response(
            {
                "notifications": unread_notification_count(request.user),
                "messages": unread_message_count(request.user),
            }
        )


class ChangePasswordView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    throttle_scope = "auth"

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        # The old pair just became invalid; hand this session a fresh one.
        refresh = RefreshToken.for_user(user)
        return with_refresh_cookie(
            Response({"access": str(refresh.access_token), "refresh": str(refresh)})
        )


class PasswordResetRequestView(APIView):
    """Send a reset link. Always 204 so account existence isn't leaked."""

    permission_classes = (permissions.AllowAny,)
    throttle_scope = "auth"

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(
            email__iexact=serializer.validated_data["email"], is_active=True
        ).first()
        if user:
            send_password_reset_email(user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetConfirmView(APIView):
    permission_classes = (permissions.AllowAny,)
    throttle_scope = "auth"

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class EmailVerifyView(APIView):
    permission_classes = (permissions.AllowAny,)
    throttle_scope = "auth"

    def post(self, request):
        serializer = EmailVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response({"email_verified": user.email_verified})


class ResendVerificationView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    throttle_scope = "auth"

    def post(self, request):
        if not request.user.email_verified:
            send_verification_email(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(cache_page(300), name="dispatch")
@method_decorator(vary_on_headers("Authorization"), name="dispatch")
class LeaderboardView(generics.ListAPIView):
    """Top users by total karma."""

    serializer_class = PublicUserSerializer
    permission_classes = (permissions.AllowAny,)
    pagination_class = None

    def get_queryset(self):
        users = User.objects.filter(is_active=True).annotate(
            karma=F("post_karma") + F("comment_karma")
        )
        return with_social_annotations(users, self.request.user).order_by("-karma", "username")[:10]


class UserProfileView(generics.RetrieveAPIView):
    serializer_class = PublicUserSerializer
    permission_classes = (permissions.AllowAny,)
    lookup_field = "username__iexact"
    lookup_url_kwarg = "username"

    def get_queryset(self):
        return with_social_annotations(User.objects.filter(is_active=True), self.request.user)

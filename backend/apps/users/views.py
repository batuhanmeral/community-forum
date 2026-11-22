from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotAuthenticated, ValidationError
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.messaging.services import unread_message_count
from apps.modmail.services import unread_modmail_count
from apps.notifications.services import unread_notification_count
from apps.social.services import with_social_annotations

from .auth_cookie import clear_refresh_cookie, refresh_from_cookie, with_refresh_cookie
from .emails import send_password_reset_email, send_verification_email
from .models import MfaDevice, MfaRecoveryCode
from .serializers import (
    AccountDeleteSerializer,
    ChangePasswordSerializer,
    EmailVerifySerializer,
    MfaAwareTokenObtainPairSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PublicUserSerializer,
    RegisterSerializer,
    RevocationAwareTokenRefreshSerializer,
    UserSerializer,
)
from .services import (
    delete_account,
    delete_file_on_commit,
    end_realtime_sessions,
    export_account,
)
from .services import delete_account, delete_file_on_commit, export_account

User = get_user_model()


class LoginView(TokenObtainPairView):
    serializer_class = MfaAwareTokenObtainPairSerializer
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
            refresh = RefreshToken(token)
            refresh.blacklist()
        except TokenError:
            pass  # Already dead; the cookie is cleared below either way.
        else:
            # Only a live session ends its sockets, so a stale cookie cannot disconnect anyone.
            end_realtime_sessions(refresh[jwt_settings.USER_ID_CLAIM])
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
                "modmail": unread_modmail_count(request.user),
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
        refresh = NexusRefreshToken.for_user(user)
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


# ── two-factor authentication ─────────────────────────────────────────────────

MFA_GENERIC_FAILURE = {"detail": "Invalid or expired verification."}


def _mfa_unavailable() -> Response:
    return Response(
        {"detail": "Two-factor authentication is not available on this server."},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def _client_ip(request) -> str | None:
    # DRF resolves this through NUM_PROXIES, so a spoofed X-Forwarded-For is not trusted.
    from rest_framework.throttling import BaseThrottle

    return BaseThrottle().get_ident(request) or None


def _session_response(user, **extra) -> Response:
    """A fresh access token plus the refresh cookie, like a normal login."""
    refresh = NexusRefreshToken.for_user(user)
    data = {"access": str(refresh.access_token), "refresh": str(refresh), **extra}
    return with_refresh_cookie(Response(data))


class MfaVerifyView(APIView):
    """Second login step: exchange the mfa_token plus a TOTP or recovery code for a session.

    Every problem with the token or the code answers the same 401 body, so nothing tells an
    attacker which part was wrong. A locked-out user gets 429.
    """

    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()
    parser_classes = (JSONParser,)
    throttle_scope = "mfa"

    def post(self, request):
        from . import mfa

        generic = Response(MFA_GENERIC_FAILURE, status=status.HTTP_401_UNAUTHORIZED)
        token = request.data.get("mfa_token") if hasattr(request.data, "get") else None
        code = request.data.get("code") if hasattr(request.data, "get") else None
        if not isinstance(token, str) or not isinstance(code, str):
            return generic
        challenge = mfa.load_challenge(token)
        if challenge is None:
            return generic
        # Claim an attempt first (atomic), so parallel requests cannot exceed the per-token cap.
        if not mfa.reserve_attempt(challenge):
            return generic
        user = challenge.user
        method = mfa.verify_second_factor(user, code, ip=_client_ip(request), kind="verify")
        if method is None:
            return generic
        if not mfa.consume_challenge(challenge):
            return generic  # lost a race against another use of the same challenge
        extra = (
            {"recovery_codes_remaining": mfa.recovery_codes_remaining(user)}
            if method == "recovery"
            else {}
        )
        return _session_response(user, **extra)


class _MfaManageView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    throttle_scope = "auth"
    parser_classes = (JSONParser,)

    def _check_password(self, request):
        password = request.data.get("password")
        if not isinstance(password, str) or not request.user.check_password(password):
            raise ValidationError({"password": ["Password is incorrect."]})

    def _check_code(self, request) -> None:
        from . import mfa

        code = request.data.get("code")
        method = (
            mfa.verify_second_factor(request.user, code, ip=_client_ip(request), kind="manage")
            if isinstance(code, str)
            else None
        )
        if method is None:
            raise ValidationError({"code": ["Invalid code."]})

    def dispatch(self, request, *args, **kwargs):
        from . import mfa

        try:
            return super().dispatch(request, *args, **kwargs)
        except mfa.MfaUnavailable:
            return _mfa_unavailable()


class MfaStatusView(_MfaManageView):
    def get(self, request):
        from . import mfa

        enabled = MfaDevice.objects.filter(user=request.user, confirmed_at__isnull=False).exists()
        return Response(
            {
                "available": mfa.mfa_available(),
                "enabled": enabled,
                "recovery_codes_remaining": mfa.recovery_codes_remaining(request.user)
                if enabled
                else 0,
            }
        )


class MfaSetupView(_MfaManageView):
    """Start enrolment: a pending secret, shown once as a URI/QR. Needs the password."""

    def post(self, request):
        from . import mfa

        if not mfa.mfa_available():
            return _mfa_unavailable()
        self._check_password(request)
        if MfaDevice.objects.filter(user=request.user, confirmed_at__isnull=False).exists():
            return Response(
                {"detail": "Two-factor authentication is already enabled."},
                status=status.HTTP_409_CONFLICT,
            )
        secret = mfa.new_secret()
        MfaDevice.objects.update_or_create(
            user=request.user,
            defaults={
                "secret_encrypted": mfa.encrypt_secret(secret),
                "confirmed_at": None,
                "last_used_step": 0,
            },
        )
        uri = mfa.provisioning_uri(request.user.username, secret)
        return Response({"secret": secret, "otpauth_uri": uri, "qr_data_uri": mfa.qr_data_uri(uri)})


class MfaConfirmView(_MfaManageView):
    """Finish enrolment with the first code; hands out the recovery codes once."""

    def post(self, request):
        from . import mfa

        if not mfa.mfa_available():
            return _mfa_unavailable()
        device = MfaDevice.objects.filter(user=request.user, confirmed_at__isnull=True).first()
        code = request.data.get("code")
        if device is None or not isinstance(code, str):
            raise ValidationError({"code": ["Start the setup first."]})
        secret = mfa.decrypt_secret(device.secret_encrypted)

        def check():
            digits = mfa.normalize_totp(code)
            step = mfa.matching_step(secret, digits) if digits else None
            return "totp" if step is not None and mfa.consume_step(device, step) else None

        if mfa.guarded_attempt(request.user, _client_ip(request), "confirm", check) is None:
            raise ValidationError({"code": ["Invalid code."]})
        MfaDevice.objects.filter(pk=device.pk).update(confirmed_at=timezone.now())
        codes = mfa.replace_recovery_codes(request.user)
        mfa.revoke_all_sessions(request.user)
        return _session_response(request.user, recovery_codes=codes)


class MfaDisableView(_MfaManageView):
    def post(self, request):
        from . import mfa

        self._check_password(request)
        self._check_code(request)
        MfaDevice.objects.filter(user=request.user).delete()
        MfaRecoveryCode.objects.filter(user=request.user).delete()
        mfa.revoke_all_sessions(request.user)
        return _session_response(request.user)


class MfaRecoveryCodesView(_MfaManageView):
    """Replace every recovery code. Needs the password and a current code."""

    def post(self, request):
        from . import mfa

        if not MfaDevice.objects.filter(user=request.user, confirmed_at__isnull=False).exists():
            raise ValidationError({"detail": ["Two-factor authentication is not enabled."]})
        self._check_password(request)
        self._check_code(request)
        codes = mfa.replace_recovery_codes(request.user)
        mfa.revoke_all_sessions(request.user)
        return _session_response(request.user, recovery_codes=codes)

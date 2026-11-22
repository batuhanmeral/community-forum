from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.throttling import WriteThrottleMixin

from . import vapid
from .models import MAX_SUBSCRIPTIONS_PER_USER, PushPreference, PushSubscription
from .serializers import PreferenceSerializer, SubscribeSerializer, UnsubscribeSerializer
from .tasks import GROUPS

User = get_user_model()


class PushConfigView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        from django.conf import settings

        enabled = vapid.push_enabled()
        return Response(
            {"enabled": enabled, "public_key": settings.VAPID_PUBLIC_KEY if enabled else ""}
        )


class SubscriptionView(WriteThrottleMixin, APIView):
    permission_classes = (permissions.IsAuthenticated,)
    throttle_scope = "write"

    def post(self, request):
        if not vapid.push_enabled():
            return Response(
                {"detail": "Push notifications are not available on this server."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        data = SubscribeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        with transaction.atomic():
            # Serialise per user so concurrent subscribes cannot overshoot the cap.
            User.objects.select_for_update().get(pk=request.user.pk)
            # A browser is one endpoint: if another account used it before, it moves here.
            PushSubscription.objects.filter(endpoint=values["endpoint"]).exclude(
                user=request.user
            ).delete()
            known = PushSubscription.objects.filter(
                user=request.user, endpoint=values["endpoint"]
            ).exists()
            if (
                not known
                and PushSubscription.objects.filter(user=request.user).count()
                >= MAX_SUBSCRIPTIONS_PER_USER
            ):
                raise ValidationError(
                    f"You can have at most {MAX_SUBSCRIPTIONS_PER_USER} push subscriptions."
                )
            PushSubscription.objects.update_or_create(
                endpoint=values["endpoint"],
                defaults={
                    "user": request.user,
                    "p256dh": values["p256dh"],
                    "auth": values["auth"],
                    "user_agent": request.META.get("HTTP_USER_AGENT", "")[:255],
                    "failures": 0,
                    "session_id": str(getattr(request.auth, "get", lambda *_: "")("sid", ""))[:64],
                },
            )
        return Response(status=status.HTTP_201_CREATED)

    def delete(self, request):
        data = UnsubscribeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        PushSubscription.objects.filter(
            user=request.user, endpoint=data.validated_data["endpoint"]
        ).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def _preference_payload(preference: PushPreference | None) -> dict:
    disabled = set(preference.disabled_groups) if preference else set()
    return {
        "enabled": preference.enabled if preference else True,
        "types": {group: group not in disabled for group in GROUPS},
    }


class PreferencesView(WriteThrottleMixin, APIView):
    permission_classes = (permissions.IsAuthenticated,)
    throttle_scope = "write"

    def get(self, request):
        preference = PushPreference.objects.filter(user=request.user).first()
        return Response(_preference_payload(preference))

    def put(self, request):
        data = PreferenceSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        preference, _ = PushPreference.objects.get_or_create(user=request.user)
        if "enabled" in data.validated_data:
            preference.enabled = data.validated_data["enabled"]
        disabled = set(preference.disabled_groups)
        for group, on in data.validated_data.get("types", {}).items():
            (disabled.discard if on else disabled.add)(group)
        preference.disabled_groups = sorted(disabled)
        preference.save()
        return Response(_preference_payload(preference))

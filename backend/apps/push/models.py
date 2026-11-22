from django.conf import settings
from django.db import models

MAX_SUBSCRIPTIONS_PER_USER = 10


class PushSubscription(models.Model):
    """One browser's Web Push endpoint. The keys let only us encrypt messages for that browser."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="push_subscriptions"
    )
    # Unique across users: a shared browser can only ever notify whoever subscribed last.
    endpoint = models.CharField(max_length=500, unique=True)
    p256dh = models.CharField(max_length=128)
    auth = models.CharField(max_length=64)
    user_agent = models.CharField(max_length=255, blank=True, default="")
    # Login session (the "sid" token claim) that registered it; logout removes its subscriptions.
    session_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    created = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(null=True, blank=True)
    # Consecutive failed sends; the subscription is dropped after sender.MAX_FAILURES.
    failures = models.PositiveSmallIntegerField(default=0)

    class Meta:
        indexes = [models.Index(fields=("user", "created"))]

    def __str__(self) -> str:
        return f"push subscription of user {self.user_id}"


class PushPreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="push_preference"
    )
    enabled = models.BooleanField(default=True)
    # Notification groups (see apps.push.tasks.GROUPS) the user switched off.
    disabled_groups = models.JSONField(default=list, blank=True)

    def __str__(self) -> str:
        return f"push preferences of user {self.user_id}"

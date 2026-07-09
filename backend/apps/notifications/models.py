from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Notification(models.Model):
    class Verb(models.TextChoices):
        COMMENT = "comment", "Comment"
        REPLY = "reply", "Reply"
        MENTION = "mention", "Mention"
        FOLLOW = "follow", "Follow"
        VOTE = "vote", "Vote"
        DM = "dm", "DM"
        MOD_ACTION = "mod_action", "Mod action"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="actions",
    )
    verb = models.CharField(max_length=16, choices=Verb.choices)
    target_ct = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True
    )
    target_id = models.PositiveBigIntegerField(null=True, blank=True)
    target = GenericForeignKey("target_ct", "target_id")
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("recipient", "read_at")),
        ]

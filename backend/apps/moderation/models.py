from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Report(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        RESOLVED = "resolved", "Resolved"
        DISMISSED = "dismissed", "Dismissed"

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reports_filed",
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    target = GenericForeignKey("content_type", "object_id")
    reason = models.CharField(max_length=255)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("content_type", "object_id")),
            models.Index(fields=("status",)),
        ]

    def __str__(self) -> str:
        return f"report #{self.pk} [{self.status}] {self.reason[:40]}"


class ModAction(models.Model):
    """Audit log entry for a moderator action inside a community."""

    class Action(models.TextChoices):
        USER_FLAIR_CREATE = "user_flair_create", "User flair created"
        USER_FLAIR_UPDATE = "user_flair_update", "User flair updated"
        USER_FLAIR_DELETE = "user_flair_delete", "User flair deleted"
        USER_FLAIR_ASSIGN = "user_flair_assign", "User flair assigned"
        POST_PIN = "post_pin", "Post pinned"
        POST_UNPIN = "post_unpin", "Post unpinned"
        POST_SPOILER = "post_spoiler", "Post marked spoiler"
        POST_UNSPOILER = "post_unspoiler", "Post spoiler cleared"
        POST_APPROVE = "post_approve", "Post approved"
        POST_REJECT = "post_reject", "Post rejected"
        POST_REMOVE = "post_remove", "Post removed"
        COMMENT_REMOVE = "comment_remove", "Comment removed"
        USER_BAN = "user_ban", "User banned"
        USER_UNBAN = "user_unban", "User unbanned"
        ROLE_CHANGE = "role_change", "Role changed"
        REPORT_RESOLVE = "report_resolve", "Report resolved"
        REPORT_DISMISS = "report_dismiss", "Report dismissed"
        AUTOMOD_HOLD = "automod_hold", "Held by AutoMod"

    community = models.ForeignKey(
        "communities.Community", on_delete=models.CASCADE, related_name="mod_actions"
    )
    # Null actor = automated action (AutoMod).
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mod_actions",
    )
    action = models.CharField(max_length=32, choices=Action.choices)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveBigIntegerField(null=True, blank=True)
    target = GenericForeignKey("content_type", "object_id")
    detail = models.CharField(max_length=255, blank=True, default="")
    # Copied from the removal reason at action time so later template edits never rewrite history.
    reason_title = models.CharField(max_length=60, blank=True, default="")
    reason_body = models.CharField(max_length=1000, blank=True, default="")
    reason_note = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("community", "-created_at"))]

    def __str__(self) -> str:
        return f"{self.community_id}: {self.action} by {self.actor_id or 'automod'}"


class RemovalReason(models.Model):
    """Moderator-managed template offered when removing someone else's content."""

    community = models.ForeignKey(
        "communities.Community", on_delete=models.CASCADE, related_name="removal_reasons"
    )
    title = models.CharField(max_length=60)
    body = models.CharField(max_length=1000)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("order", "id")
        indexes = [models.Index(fields=("community", "order"))]

    def __str__(self) -> str:
        return self.title

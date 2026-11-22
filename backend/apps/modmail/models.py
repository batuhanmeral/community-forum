from django.conf import settings
from django.db import models


class ModmailThread(models.Model):
    """A conversation between one user and a community's moderator team."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ARCHIVED = "archived", "Archived"

    community = models.ForeignKey(
        "communities.Community", on_delete=models.CASCADE, related_name="modmail_threads"
    )
    # Accounts are erased in place (the row stays), so SET_NULL only guards hard deletes.
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="modmail_threads",
    )
    subject = models.CharField(max_length=100)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_modmail_threads",
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated", "-id")
        indexes = [
            models.Index(fields=("community", "status", "-updated")),
            models.Index(fields=("creator", "-updated")),
            models.Index(fields=("creator", "community", "created")),
        ]

    def __str__(self) -> str:
        return f"modmail #{self.pk} {self.subject[:40]}"


class ModmailMessage(models.Model):
    thread = models.ForeignKey(ModmailThread, on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="modmail_messages",
    )
    body = models.CharField(max_length=5000)
    # Moderator-only note; never serialized for the thread creator.
    is_internal = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("id",)
        indexes = [models.Index(fields=("thread", "id"))]

    def __str__(self) -> str:
        return f"message #{self.pk} in thread {self.thread_id}"


class ModmailRead(models.Model):
    """Per-user read marker: the newest message the user has seen in a thread."""

    thread = models.ForeignKey(ModmailThread, on_delete=models.CASCADE, related_name="reads")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="modmail_reads"
    )
    last_read_message_id = models.PositiveBigIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("thread", "user"), name="modmail_read_unique")
        ]

    def __str__(self) -> str:
        return f"user {self.user_id} read thread {self.thread_id}"

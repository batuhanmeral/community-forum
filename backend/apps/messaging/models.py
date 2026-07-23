from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Conversation(models.Model):
    participant_a = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversations_as_a",
    )
    participant_b = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversations_as_b",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("participant_a", "participant_b")

    def __str__(self) -> str:
        return f"conversation {self.participant_a_id} ↔ {self.participant_b_id}"

    def save(self, *args, **kwargs):
        if (
            self.participant_a_id
            and self.participant_b_id
            and self.participant_a_id > self.participant_b_id
        ):
            self.participant_a_id, self.participant_b_id = (
                self.participant_b_id,
                self.participant_a_id,
            )
        super().save(*args, **kwargs)

    def clean(self) -> None:
        if self.participant_a_id == self.participant_b_id:
            raise ValidationError("Participants must differ.")
        if (
            self.participant_a_id
            and self.participant_b_id
            and self.participant_a_id > self.participant_b_id
        ):
            raise ValidationError("participant_a must have the lower id.")


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_messages"
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("created_at",)
        indexes = [
            models.Index(fields=("conversation", "created_at")),
        ]

    def __str__(self) -> str:
        return f"message {self.pk} in conversation {self.conversation_id}"

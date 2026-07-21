from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Follow(models.Model):
    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="following",
    )
    followed = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="followers",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("follower", "followed")

    def __str__(self) -> str:
        return f"{self.follower_id} → {self.followed_id}"

    def clean(self) -> None:
        if self.follower_id == self.followed_id:
            raise ValidationError("Users cannot follow themselves.")


class Block(models.Model):
    blocker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocks",
    )
    blocked = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocked_by",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("blocker", "blocked")

    def __str__(self) -> str:
        return f"{self.blocker_id} ⊘ {self.blocked_id}"

    def clean(self) -> None:
        if self.blocker_id == self.blocked_id:
            raise ValidationError("Users cannot block themselves.")


def is_blocked_between(user_a, user_b) -> bool:
    """True if either user has blocked the other."""
    return Block.objects.filter(
        models.Q(blocker=user_a, blocked=user_b) | models.Q(blocker=user_b, blocked=user_a)
    ).exists()

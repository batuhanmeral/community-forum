from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from apps.posts.models import Post


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments"
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies",
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    votes = GenericRelation(
        "votes.Vote", content_type_field="content_type", object_id_field="object_id"
    )
    saves = GenericRelation(
        "saves.SavedItem", content_type_field="content_type", object_id_field="object_id"
    )

    class Meta:
        ordering = ("created_at",)
        indexes = [
            models.Index(fields=("post", "created_at")),
        ]

    def __str__(self) -> str:
        return f"Comment by {self.author} on {self.post_id}"

from django.conf import settings
from django.db import models

from apps.communities.models import Community, Flair


class Post(models.Model):
    class Kind(models.TextChoices):
        TEXT = "text", "Text"
        LINK = "link", "Link"
        IMAGE = "image", "Image"
        POLL = "poll", "Poll"

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts"
    )
    community = models.ForeignKey(
        Community, on_delete=models.CASCADE, related_name="posts"
    )
    flair = models.ForeignKey(
        Flair,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="posts",
    )
    kind = models.CharField(max_length=8, choices=Kind.choices, default=Kind.TEXT)
    title = models.CharField(max_length=300)
    body = models.TextField(blank=True, default="")
    url = models.URLField(blank=True, default="")
    image = models.ImageField(upload_to="posts/", blank=True, null=True)
    is_nsfw = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-is_pinned", "-created_at")
        indexes = [
            models.Index(fields=("community", "-created_at")),
        ]

    def __str__(self) -> str:
        return self.title

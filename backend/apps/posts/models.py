from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
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
    edited_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    search_vector = SearchVectorField(null=True, blank=True)

    votes = GenericRelation(
        "votes.Vote", content_type_field="content_type", object_id_field="object_id"
    )
    saves = GenericRelation(
        "saves.SavedItem", content_type_field="content_type", object_id_field="object_id"
    )

    class Meta:
        ordering = ("-is_pinned", "-created_at")
        indexes = [
            models.Index(fields=("community", "-created_at")),
            GinIndex(fields=("search_vector",), name="posts_post_search_gin"),
        ]

    def __str__(self) -> str:
        return self.title


class PostRevision(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="revisions")
    title = models.CharField(max_length=300)
    body = models.TextField(blank=True, default="")
    edited_at = models.DateTimeField(auto_now_add=True)
    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        ordering = ("-edited_at",)
        indexes = [models.Index(fields=("post", "-edited_at"))]

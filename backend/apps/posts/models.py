from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models

from apps.common.rendered_body import RenderedBodyModel
from apps.communities.models import Community, Flair


class Post(RenderedBodyModel):
    class Kind(models.TextChoices):
        TEXT = "text", "Text"
        LINK = "link", "Link"
        IMAGE = "image", "Image"
        POLL = "poll", "Poll"

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts"
    )
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="posts")
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
    is_question = models.BooleanField(default=False)
    accepted_comment = models.ForeignKey(
        "comments.Comment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accepted_for",
    )
    bounty_amount = models.PositiveSmallIntegerField(default=0)
    bounty_expires_at = models.DateTimeField(null=True, blank=True)
    bounty_status = models.CharField(max_length=8, default="", blank=True)
    image = models.ImageField(upload_to="posts/", blank=True, null=True)
    is_nsfw = models.BooleanField(default=False)
    is_spoiler = models.BooleanField(default=False)
    crosspost_parent = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="crossposts"
    )
    is_pinned = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=True)
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
        constraints = [
            # One live crosspost of a root per user and community; deleting it frees the slot.
            models.UniqueConstraint(
                fields=("author", "crosspost_parent", "community"),
                condition=models.Q(crosspost_parent__isnull=False, deleted_at__isnull=True),
                name="posts_one_crosspost_per_user_root_community",
            ),
        ]
        indexes = [
            models.Index(fields=("community", "-created_at")),
            models.Index(
                fields=("bounty_status", "bounty_expires_at"), name="qa_bounty_expiry_idx"
            ),
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

    def __str__(self) -> str:
        return f"rev of post {self.post_id} @ {self.edited_at:%Y-%m-%d %H:%M}"


class HiddenPost(models.Model):
    """A post a user hid from their own feeds; profile pages and direct links are unaffected."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="hidden_posts"
    )
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="hidden_by")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("user", "post"), name="posts_hiddenpost_user_post_uniq")
        ]
        indexes = [models.Index(fields=("user", "-created"), name="posts_hidden_user_created_idx")]

    def __str__(self) -> str:
        return f"user {self.user_id} hid post {self.post_id}"


class FeedExclusion(models.Model):
    """A community a user keeps out of their Popular/All and trending lists (not Home)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="feed_exclusions"
    )
    community = models.ForeignKey(
        Community, on_delete=models.CASCADE, related_name="feed_exclusions"
    )
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("user", "community"), name="posts_feedexclusion_user_community_uniq"
            )
        ]

    def __str__(self) -> str:
        return f"user {self.user_id} excludes community {self.community_id}"

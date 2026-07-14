from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models


class Community(models.Model):
    slug = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default="")
    avatar = models.ImageField(upload_to="community_avatars/", blank=True, null=True)
    is_nsfw = models.BooleanField(default=False)
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_communities",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    search_vector = SearchVectorField(null=True, blank=True)

    class Meta:
        indexes = [
            GinIndex(fields=("search_vector",), name="communities_search_gin"),
        ]

    def __str__(self) -> str:
        return self.slug


class Membership(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        MODERATOR = "moderator", "Moderator"
        MEMBER = "member", "Member"

    class NotifyLevel(models.TextChoices):
        ALL = "all", "All"
        POSTS_ONLY = "posts_only", "Posts only"
        OFF = "off", "Off"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.MEMBER)
    notify_level = models.CharField(
        max_length=16, choices=NotifyLevel.choices, default=NotifyLevel.ALL
    )
    is_banned = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "community")

    def __str__(self) -> str:
        return f"{self.user} @ {self.community} ({self.role})"


class Flair(models.Model):
    community = models.ForeignKey(
        Community, on_delete=models.CASCADE, related_name="flairs"
    )
    name = models.CharField(max_length=50)
    color = models.CharField(max_length=7, default="#888888")

    class Meta:
        unique_together = ("community", "name")

    def __str__(self) -> str:
        return f"{self.community.slug}:{self.name}"

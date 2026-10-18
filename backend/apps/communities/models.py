from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.core.validators import RegexValidator
from django.db import models

HEX_COLOR_PATTERN = r"^#[0-9a-fA-F]{6}\Z"
DEFAULT_FLAIR_COLOR = "#888888"


class Community(models.Model):
    slug = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=500, blank=True, default="")
    avatar = models.ImageField(upload_to="community_avatars/", blank=True, null=True)
    is_nsfw = models.BooleanField(default=False)
    requires_approval = models.BooleanField(default=False)
    # AutoMod: newline-separated keywords; matching posts are held for mod approval.
    banned_keywords = models.CharField(max_length=2000, blank=True, default="")
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

    def banned_keyword_list(self) -> list[str]:
        return [kw.strip().lower() for kw in self.banned_keywords.splitlines() if kw.strip()]

    def matches_banned_keyword(self, *texts: str) -> str | None:
        """Return the first banned keyword found in any of the given texts, if any."""
        keywords = self.banned_keyword_list()
        if not keywords:
            return None
        haystack = " ".join(t.lower() for t in texts if t)
        for kw in keywords:
            if kw in haystack:
                return kw
        return None

    def banned_keyword_added(self, before: tuple[str, ...], after: tuple[str, ...]) -> str | None:
        """First banned keyword present in `after` but not in `before`."""
        old = " ".join(t.lower() for t in before if t)
        new = " ".join(t.lower() for t in after if t)
        for kw in self.banned_keyword_list():
            if kw in new and kw not in old:
                return kw
        return None


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
    # Who issued the ban: lifting it needs at least their rank (null = issued before this was recorded).
    banned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    banned_at = models.DateTimeField(null=True, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "community")

    def __str__(self) -> str:
        return f"{self.user} @ {self.community} ({self.role})"


class CommunityRule(models.Model):
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="rules")
    order = models.PositiveSmallIntegerField(default=0)
    short = models.CharField(max_length=100)
    description = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("order", "id")
        indexes = [models.Index(fields=("community", "order"))]

    def __str__(self) -> str:
        return f"{self.community.slug}: {self.short}"


class Flair(models.Model):
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="flairs")
    name = models.CharField(max_length=50)
    color = models.CharField(
        max_length=7,
        default=DEFAULT_FLAIR_COLOR,
        validators=[RegexValidator(HEX_COLOR_PATTERN)],
    )

    class Meta:
        unique_together = ("community", "name")

    def __str__(self) -> str:
        return f"{self.community.slug}:{self.name}"

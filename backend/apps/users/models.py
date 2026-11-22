from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from .validators import username_validator, validate_country_code


class User(AbstractUser):
    username = models.CharField(
        _("username"),
        max_length=150,
        unique=True,
        help_text=_("3-30 characters: letters, digits and underscores."),
        validators=[username_validator],
        error_messages={"unique": _("A user with that username already exists.")},
    )
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    bio = models.CharField(max_length=500, blank=True, default="")
    country = models.CharField(
        max_length=2, blank=True, default="", validators=[validate_country_code]
    )
    post_karma = models.IntegerField(default=0)
    comment_karma = models.IntegerField(default=0)
    show_nsfw = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)
    # Bumped by logout: realtime sockets and tickets bound to an older value are revoked. Kept in
    # the database because a cache entry could be evicted and quietly re-validate old sockets.
    # Big so it never runs out; db_default so app instances predating the column can still insert
    # users during a rolling deploy.
    realtime_generation = models.PositiveBigIntegerField(default=0, db_default=0, editable=False)
    search_vector = SearchVectorField(null=True, blank=True)

    class Meta(AbstractUser.Meta):
        indexes = [
            GinIndex(fields=("search_vector",), name="users_user_search_gin"),
        ]
        constraints = [
            models.UniqueConstraint(Lower("username"), name="users_user_username_ci_unique"),
            models.UniqueConstraint(
                Lower("email"),
                condition=~models.Q(email=""),
                name="users_user_email_ci_unique",
            ),
        ]

    def __str__(self) -> str:
        return self.username


class KarmaAdjustment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="karma_adjustments")
    amount = models.IntegerField()
    reason = models.CharField(max_length=32)
    post = models.ForeignKey(
        "posts.Post", null=True, on_delete=models.SET_NULL, related_name="karma_adjustments"
    )
    comment = models.ForeignKey(
        "comments.Comment", null=True, on_delete=models.SET_NULL, related_name="karma_adjustments"
    )
    created = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=False)
    reverses = models.OneToOneField(
        "self", null=True, on_delete=models.SET_NULL, related_name="reversal"
    )

    class Meta:
        indexes = [models.Index(fields=("user", "created"), name="qa_adjustment_user_idx")]
        constraints = [
            models.UniqueConstraint(
                fields=("comment", "reason"),
                condition=models.Q(active=True),
                name="qa_one_active_comment_grant",
            ),
            models.CheckConstraint(
                condition=models.Q(active=False)
                | models.Q(amount=15, reason="answer_accepted", comment__isnull=False),
                name="qa_valid_active_grant",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.reason} {self.amount:+d} for user {self.user_id}"

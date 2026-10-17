from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from .validators import username_validator


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
    post_karma = models.IntegerField(default=0)
    comment_karma = models.IntegerField(default=0)
    show_nsfw = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)
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

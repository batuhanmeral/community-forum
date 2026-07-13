from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models


class User(AbstractUser):
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    bio = models.TextField(blank=True, default="")
    post_karma = models.IntegerField(default=0)
    comment_karma = models.IntegerField(default=0)
    search_vector = SearchVectorField(null=True, blank=True)

    class Meta(AbstractUser.Meta):
        indexes = [
            GinIndex(fields=("search_vector",), name="users_user_search_gin"),
        ]

    def __str__(self) -> str:
        return self.username

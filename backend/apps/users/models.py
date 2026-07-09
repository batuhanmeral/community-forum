from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    bio = models.TextField(blank=True, default="")
    post_karma = models.IntegerField(default=0)
    comment_karma = models.IntegerField(default=0)

    def __str__(self) -> str:
        return self.username

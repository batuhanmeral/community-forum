from django.contrib.auth import get_user_model
from django.contrib.postgres.search import SearchVector
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.communities.models import Community
from apps.posts.models import Post

User = get_user_model()


def _refresh_vector(model, pk: int, *fields_with_weights) -> None:
    """Recompute search_vector for a single row to keep it in sync."""
    vector = None
    for field, weight in fields_with_weights:
        v = SearchVector(field, weight=weight)
        vector = v if vector is None else vector + v
    model.objects.filter(pk=pk).update(search_vector=vector)


@receiver(post_save, sender=Post)
def _update_post_vector(sender, instance: Post, **kwargs):
    _refresh_vector(Post, instance.pk, ("title", "A"), ("body", "B"))


@receiver(post_save, sender=Community)
def _update_community_vector(sender, instance: Community, **kwargs):
    _refresh_vector(Community, instance.pk, ("name", "A"), ("slug", "A"), ("description", "B"))


@receiver(post_save, sender=User)
def _update_user_vector(sender, instance: User, **kwargs):
    _refresh_vector(User, instance.pk, ("username", "A"), ("bio", "B"))

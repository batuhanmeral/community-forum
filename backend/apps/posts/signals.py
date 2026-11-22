"""Keep Q&A karma and crosspost copies consistent when content is removed for good."""

from django.contrib.auth import get_user_model
from django.db.models import Case, F, QuerySet, When
from django.db.models.functions import Coalesce, Now
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from apps.comments.models import Comment

from .models import Post


def _user_is_being_deleted(origin, user_id) -> bool:
    """True when this delete started from removing the user themselves.

    Their karma ledger is cascade-deleted with them, so a reversal or refund row written for
    them now would point at a missing user.
    """
    user_model = get_user_model()
    if isinstance(origin, user_model):
        return origin.pk == user_id
    if isinstance(origin, QuerySet) and origin.model is user_model:
        return origin.filter(pk=user_id).exists()
    return False


@receiver(pre_delete, sender=Comment, dispatch_uid="qa_comment_hard_delete")
def _comment_hard_delete(sender, instance, origin=None, **kwargs):
    from . import qa

    qa.on_comment_hard_delete(
        instance.pk, reverse_karma=not _user_is_being_deleted(origin, instance.author_id)
    )


@receiver(pre_delete, sender=Post, dispatch_uid="qa_post_hard_delete")
def _post_hard_delete(sender, instance, origin=None, **kwargs):
    from . import qa

    if not _user_is_being_deleted(origin, instance.author_id):
        qa.on_post_hard_delete(instance.pk)


@receiver(pre_delete, sender=Post, dispatch_uid="crosspost_root_hard_delete")
def _crosspost_root_hard_delete(sender, instance, **kwargs):
    """Copies of a post removed for good become "[deleted]" placeholders, not plain posts.

    The FK is SET_NULL, so without this the copied title, body, link and image would live on
    as an ordinary post once the original is gone.
    """
    Post.objects.filter(crosspost_parent_id=instance.pk).update(
        deleted_at=Coalesce("deleted_at", Now()),
        # Attributed to the copy's author so it reads "[deleted]", not a moderator "[removed]";
        # a copy a moderator already removed keeps that attribution.
        deleted_by_id=Case(
            When(deleted_at__isnull=True, then=F("author_id")), default=F("deleted_by_id")
        ),
        title="[deleted]",
        body="",
        body_html="",
        url="",
        image=None,
        is_pinned=False,
    )

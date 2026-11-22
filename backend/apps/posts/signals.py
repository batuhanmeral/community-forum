
from django.contrib.auth import get_user_model
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

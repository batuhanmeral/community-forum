from django.contrib.contenttypes.models import ContentType
from django.db.models import F
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import Vote

# Map target content_type → User karma field
_KARMA_FIELDS = {
    ("posts", "post"): "post_karma",
    ("comments", "comment"): "comment_karma",
}


def _karma_field_for(ct: ContentType) -> str | None:
    return _KARMA_FIELDS.get((ct.app_label, ct.model))


def _adjust_karma(target, ct: ContentType, delta: int) -> None:
    field = _karma_field_for(ct)
    if not field or delta == 0 or target is None:
        return
    author_id = getattr(target, "author_id", None)
    if author_id is None:
        return
    type(target.author).objects.filter(pk=author_id).update(**{field: F(field) + delta})


@receiver(pre_save, sender=Vote)
def _stash_previous_value(sender, instance: Vote, **kwargs):
    if instance.pk:
        instance._previous_value = (
            Vote.objects.filter(pk=instance.pk).values_list("value", flat=True).first()
        )
    else:
        instance._previous_value = None


@receiver(post_save, sender=Vote)
def _apply_karma_on_save(sender, instance: Vote, created: bool, **kwargs):
    previous = getattr(instance, "_previous_value", None)
    delta = instance.value if created else (instance.value - (previous or 0))
    _adjust_karma(instance.target, instance.content_type, delta)


@receiver(post_delete, sender=Vote)
def _apply_karma_on_delete(sender, instance: Vote, **kwargs):
    _adjust_karma(instance.target, instance.content_type, -instance.value)

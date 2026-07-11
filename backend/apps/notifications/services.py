from django.contrib.contenttypes.models import ContentType

from .models import Notification


def notify(recipient, *, actor=None, verb: str, target=None) -> Notification | None:
    """Create a Notification; no-op if recipient == actor."""
    if recipient is None:
        return None
    if actor is not None and getattr(actor, "id", None) == getattr(recipient, "id", None):
        return None
    kwargs = {"recipient": recipient, "actor": actor, "verb": verb}
    if target is not None:
        kwargs["target_ct"] = ContentType.objects.get_for_model(target.__class__)
        kwargs["target_id"] = target.pk
    return Notification.objects.create(**kwargs)

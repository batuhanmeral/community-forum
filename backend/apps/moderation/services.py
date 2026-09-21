from django.contrib.contenttypes.models import ContentType

from .models import ModAction


def log_mod_action(community, *, actor=None, action: str, target=None, detail: str = "") -> None:
    """Append an entry to the community's moderation audit log."""
    kwargs = {"community": community, "actor": actor, "action": action, "detail": detail}
    if target is not None:
        kwargs["content_type"] = ContentType.objects.get_for_model(target.__class__)
        kwargs["object_id"] = target.pk
    ModAction.objects.create(**kwargs)

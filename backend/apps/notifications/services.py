from django.contrib.contenttypes.models import ContentType

from .models import Notification

# Verbs that bypass community notify_level (always delivered)
DIRECT_VERBS = {"reply", "mention", "follow", "dm", "mod_action"}


def _suppressed_by_notify_level(recipient, community, verb: str) -> bool:
    """Return True if recipient's notify_level on `community` mutes this verb."""
    if community is None or verb in DIRECT_VERBS:
        return False
    from apps.communities.models import Membership

    level = (
        Membership.objects.filter(user=recipient, community=community)
        .values_list("notify_level", flat=True)
        .first()
    )
    if level is None:
        return False
    if level == Membership.NotifyLevel.OFF:
        return True
    # posts_only suppresses community-activity verbs (e.g. comment); only a
    # future "post" broadcast verb would pass through. Today: suppress.
    if level == Membership.NotifyLevel.POSTS_ONLY:
        return True
    return False


def _recipient_blocked_actor(recipient, actor) -> bool:
    from apps.social.models import Block

    return Block.objects.filter(blocker=recipient, blocked=actor).exists()


def notify(
    recipient,
    *,
    actor=None,
    verb: str,
    target=None,
    community=None,
) -> Notification | None:
    """Create a Notification. Skips self-notification and respects notify_level."""
    if recipient is None:
        return None
    if actor is not None and getattr(actor, "id", None) == getattr(recipient, "id", None):
        return None
    if actor is not None and _recipient_blocked_actor(recipient, actor):
        return None
    if _suppressed_by_notify_level(recipient, community, verb):
        return None
    kwargs = {"recipient": recipient, "actor": actor, "verb": verb}
    if target is not None:
        kwargs["target_ct"] = ContentType.objects.get_for_model(target.__class__)
        kwargs["target_id"] = target.pk
    return Notification.objects.create(**kwargs)


def unread_notification_count(user) -> int:
    """Same rows as the inbox's `?unread=true` list."""
    return Notification.objects.filter(recipient=user, read_at__isnull=True).count()

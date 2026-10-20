from django.db.models import Q

from .models import Message


def unread_message_count(user) -> int:
    """Messages from the other participant not yet read, over all of the user's conversations."""
    return (
        Message.objects.filter(read_at__isnull=True)
        .filter(Q(conversation__participant_a=user) | Q(conversation__participant_b=user))
        .exclude(sender=user)
        .count()
    )

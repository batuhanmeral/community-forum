from datetime import timedelta

from django.db import transaction
from django.db.models import Exists, F, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.exceptions import Throttled, ValidationError

from apps.communities.models import Membership
from apps.communities.services import MOD_ROLES, is_moderator
from apps.notifications.services import notify
from apps.realtime.publish import publish_to_user

from .models import ModmailMessage, ModmailRead, ModmailThread

NEW_THREADS_PER_DAY = 5
MAX_MESSAGES_PER_THREAD = 300


def moderator_users(community):
    """Active moderators of the community (banned or deleted accounts never count)."""
    return [
        m.user
        for m in Membership.objects.filter(
            community=community, role__in=MOD_ROLES, is_banned=False, user__is_active=True
        ).select_related("user")
    ]


def moderated_community_ids(user):
    return Membership.objects.filter(user=user, role__in=MOD_ROLES, is_banned=False).values_list(
        "community_id", flat=True
    )


def unread_messages(user, thread_ref: str, *, include_internal: bool):
    """Messages in the referenced thread by someone else, newer than the user's read marker."""
    read = ModmailRead.objects.filter(thread=OuterRef("thread_id"), user=user).values(
        "last_read_message_id"
    )[:1]
    qs = (
        ModmailMessage.objects.filter(thread=OuterRef(thread_ref))
        .exclude(author=user)
        .annotate(last_read=Coalesce(Subquery(read), 0))
        .filter(id__gt=F("last_read"))
    )
    return qs if include_internal else qs.filter(is_internal=False)


def annotate_unread(qs, user, *, moderator_view: bool):
    return qs.annotate(unread=Exists(unread_messages(user, "pk", include_internal=moderator_view)))


def unread_modmail_count(user) -> int:
    read = ModmailRead.objects.filter(thread=OuterRef("thread_id"), user=user).values(
        "last_read_message_id"
    )[:1]
    messages = (
        ModmailMessage.objects.exclude(author=user)
        .annotate(last_read=Coalesce(Subquery(read), 0))
        .filter(id__gt=F("last_read"))
    )
    as_creator = Q(thread__creator=user, is_internal=False)
    as_mod = Q(
        thread__community_id__in=moderated_community_ids(user),
        thread__status=ModmailThread.Status.OPEN,
    )
    return messages.filter(as_creator | as_mod).values("thread_id").distinct().count()


def _announce(thread: ModmailThread, *, author, internal: bool) -> None:
    """Notify the other side and wake their open sockets."""
    mods = moderator_users(thread.community)
    event = {"type": "modmail.updated", "thread_id": thread.pk}
    audience = {m.pk for m in mods}
    # Internal notes are for the team only: the creator is not even woken up.
    if thread.creator_id and not internal:
        audience.add(thread.creator_id)
    for user_id in audience:
        publish_to_user(user_id, event)
    if internal:
        return
    if author.pk == thread.creator_id:
        assignee = next((m for m in mods if m.pk == thread.assigned_to_id), None)
        for mod in [assignee] if assignee else mods:
            # Muting the community also mutes its modmail notices for that moderator.
            notify(mod, actor=author, verb="modmail", target=thread, community=thread.community)
    elif thread.creator is not None:
        notify(thread.creator, actor=author, verb="modmail", target=thread)


@transaction.atomic
def create_thread(user, community, subject: str, body: str) -> ModmailThread:
    from django.contrib.auth import get_user_model

    # Serialise this user's creations so parallel requests cannot all pass the count below.
    get_user_model().objects.select_for_update().get(pk=user.pk)
    since = timezone.now() - timedelta(days=1)
    recent = ModmailThread.objects.filter(
        creator=user, community=community, created__gte=since
    ).count()
    if recent >= NEW_THREADS_PER_DAY:
        raise Throttled(detail="You can open at most 5 modmail threads per community per day.")
    thread = ModmailThread.objects.create(community=community, creator=user, subject=subject)
    message = ModmailMessage.objects.create(thread=thread, author=user, body=body)
    ModmailRead.objects.create(thread=thread, user=user, last_read_message_id=message.pk)
    _announce(thread, author=user, internal=False)
    return thread


@transaction.atomic
def add_message(thread: ModmailThread, author, body: str, *, internal: bool) -> ModmailMessage:
    thread = (
        ModmailThread.objects.select_for_update(of=("self",))
        .select_related("community", "creator")
        .get(pk=thread.pk)
    )
    moderator = is_moderator(author, thread.community)
    if internal and not moderator:
        raise ValidationError({"is_internal": "Only moderators can write internal notes."})
    if thread.messages.count() >= MAX_MESSAGES_PER_THREAD:
        raise ValidationError("This thread has reached its message limit.")
    message = ModmailMessage.objects.create(
        thread=thread, author=author, body=body, is_internal=internal
    )
    ModmailRead.objects.update_or_create(
        thread=thread, user=author, defaults={"last_read_message_id": message.pk}
    )
    # `updated` is visible to the creator, so an internal note must not move it.
    if not internal:
        update_fields = ["updated"]
        if author.pk == thread.creator_id:
            thread.status = ModmailThread.Status.OPEN
            update_fields.append("status")
        thread.save(update_fields=update_fields)
    _announce(thread, author=author, internal=internal)
    return message


def mark_read(thread: ModmailThread, user) -> None:
    latest = thread.messages.order_by("-id").values_list("id", flat=True).first() or 0
    ModmailRead.objects.update_or_create(
        thread=thread, user=user, defaults={"last_read_message_id": latest}
    )

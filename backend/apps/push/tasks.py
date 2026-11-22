import logging

from django.db import transaction
from django.tasks import task

from . import vapid
from .models import PushPreference, PushSubscription
from .sender import send_to_subscription

logger = logging.getLogger(__name__)

# What a user can switch on or off, as groups of notification verbs.
GROUPS = {
    "messages": {"dm"},
    # Activity on your posts and answers, Q&A outcomes included.
    "replies": {"comment", "reply", "answer_accepted", "bounty_awarded", "bounty_refunded"},
    "mentions": {"mention"},
    "follows": {"follow"},
    "moderation": {"mod_action", "removal", "modmail"},
}
# Fixed same-origin paths: a push never carries content, names or ids, only where to look.
_URLS = {"dm": "/messages", "modmail": "/modmail"}


def group_of(verb: str) -> str | None:
    return next((name for name, verbs in GROUPS.items() if verb in verbs), None)


def payload_for(verb: str) -> dict:
    return {"type": verb, "url": _URLS.get(verb, "/inbox"), "tag": verb}


@task()
def deliver_push(notification_id: int) -> None:
    from apps.notifications.models import Notification

    if not vapid.push_enabled():
        return
    notification = (
        Notification.objects.select_related("recipient").filter(pk=notification_id).first()
    )
    if notification is None or not notification.recipient.is_active:
        return
    group = group_of(notification.verb)
    preference = PushPreference.objects.filter(user=notification.recipient).first()
    if group is None or (
        preference is not None and (not preference.enabled or group in preference.disabled_groups)
    ):
        return
    payload = payload_for(notification.verb)
    for subscription in PushSubscription.objects.filter(user=notification.recipient):
        send_to_subscription(subscription, payload)


def enqueue_push(notification) -> None:
    """Queue delivery after the notification row is committed. Never raises into the request."""
    if not vapid.push_enabled():
        return
    notification_id = notification.pk

    def _enqueue():
        try:
            deliver_push.enqueue(notification_id)
        except Exception as exc:
            logger.error("Push queue unavailable (error=%s)", type(exc).__name__)

    transaction.on_commit(_enqueue)

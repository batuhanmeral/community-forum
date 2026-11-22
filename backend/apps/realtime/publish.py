"""Publish wake-up events to a user's open sockets.

Events carry a type and ids only; clients refetch through the REST API, which keeps every
permission, block and NSFW rule in one place. Delivery is best effort: it runs after commit (so a
rolled-back change is never announced), is bounded by REALTIME_PUBLISH_TIMEOUT, and a failure is
logged instead of breaking the request. Clients resync on reconnect and keep a slow poll.
"""

import asyncio
import logging
from functools import partial

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import transaction

from .groups import realtime_enabled, user_group

logger = logging.getLogger(__name__)


def publish_to_user(user_id: int, event: dict) -> None:
    """Send `event` (e.g. {"type": "message.created", "conversation_id": 3}) once committed."""
    _send_on_commit(user_id, {"type": "realtime.event", "event": event})


def revoke_sessions(user_id: int) -> None:
    """Close every open socket of the user once committed (password change, deletion...)."""
    _send_on_commit(user_id, {"type": "session.revoked"})


def _send_on_commit(user_id: int, message: dict) -> None:
    if realtime_enabled():
        transaction.on_commit(partial(_send, user_id, message))


def _send(user_id: int, message: dict) -> None:
    try:
        async_to_sync(_group_send)(user_group(user_id), message)
    except Exception:
        logger.warning("Realtime publish to user %s failed", user_id, exc_info=True)


async def _group_send(group: str, message: dict) -> None:
    layer = get_channel_layer()
    await asyncio.wait_for(
        layer.group_send(group, message), timeout=settings.REALTIME_PUBLISH_TIMEOUT
    )

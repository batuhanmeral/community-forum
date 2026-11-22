import asyncio
import json
import logging
import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings
from django.contrib.auth import get_user_model

from . import admission
from .groups import user_group
from .sessions import USER_FIELDS, still_matches
from .tickets import aconsume_ticket

logger = logging.getLogger(__name__)

# Application close codes (4000-4999). Clients reconnect with a fresh ticket after any of them.
AUTH_FAILED = 4001
# The access token that bought the ticket expired; the client reconnects after refreshing it.
TOKEN_EXPIRED = 4002
SESSION_REVOKED = 4003
# The user already has REALTIME_MAX_SOCKETS_PER_USER sockets open.
TOO_MANY_CONNECTIONS = 4029
# The user's session could not be checked (database down); fail closed.
INTERNAL_ERROR = 1011

# Clients only ever send {"type": "auth", "ticket": ...} and {"type": "ping"}.
MAX_FRAME_CHARS = 1024


@database_sync_to_async
def _load_user(user_id):
    return get_user_model().objects.filter(pk=user_id).only(*USER_FIELDS).first()


class StreamConsumer(AsyncJsonWebsocketConsumer):
    """Per-user stream of wake-up events ("something changed, refetch over REST").

    The socket is accepted unauthenticated; the first frame must be an auth message carrying a
    one-time ticket, and the whole handshake must finish within REALTIME_AUTH_TIMEOUT seconds.
    Once registered, the server re-checks the user on its own timer and before every event, so a
    revocation does not depend on the client's pings or on the revocation event arriving.
    Admission is capped (admission.py): unauthenticated sockets per process, sockets per user.
    Events never carry content.
    """

    user_id = None
    _session = None
    _closed = False
    _registered = False
    _joined = False
    _auth_started = False
    _pending = False
    _slot = None
    _auth_deadline = None
    _token_expiry = None
    _watchdog = None

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            # However the consumer ended (even a crash that skipped disconnect), give back its
            # place among unauthenticated sockets; a leaked one would shrink the cap for good.
            # Its timers stop; its slot and group membership expire on their own.
            self._leave_pending()
            if self._auth_deadline is not None:
                self._auth_deadline.cancel()
            if self._token_expiry is not None:
                self._token_expiry.cancel()
            if self._watchdog is not None:
                self._watchdog.cancel()

    async def connect(self):
        if self.channel_layer is None:
            # Realtime is off (no REDIS_URL); refusing makes the client keep polling.
            await self.close()
            return
        if not admission.enter_pending():
            # Refused before the handshake completes: costs the server nothing further.
            await self.close()
            return
        self._pending = True
        await self.accept()
        self._auth_deadline = asyncio.get_running_loop().call_later(
            settings.REALTIME_AUTH_TIMEOUT,
            lambda: asyncio.ensure_future(self._shutdown(AUTH_FAILED)),
        )

    async def disconnect(self, code):
        self._closed = True
        await self._leave()

    async def receive(self, text_data=None, bytes_data=None, **kwargs):
        if self._closed:
            return
        message = self._parse(text_data)
        if not self._auth_started:
            self._auth_started = True
            try:
                await self._authenticate(message)
            except Exception:
                logger.warning("Realtime authentication failed unexpectedly", exc_info=True)
                await self._shutdown(INTERNAL_ERROR)
        elif self._registered and message.get("type") == "ping":
            await self.send_json({"type": "pong"})
        # Anything else is ignored.

    @staticmethod
    def _parse(text_data) -> dict:
        if not isinstance(text_data, str) or len(text_data) > MAX_FRAME_CHARS:
            return {}
        try:
            message = json.loads(text_data)
        except ValueError:
            return {}
        return message if isinstance(message, dict) else {}

    async def _authenticate(self, message: dict) -> None:
        # Exactly one attempt: the first frame either authenticates or ends the socket. The auth
        # deadline keeps running until registration; after every await, a socket it closed
        # meanwhile undoes whatever the step acquired.
        claim = None
        if message.get("type") == "auth":
            claim = await aconsume_ticket(message.get("ticket"))
        user = await _load_user(claim.user_id) if claim is not None else None
        if await self._abandoned():
            return
        # The ticket must still describe the user's session: a password change or logout since it
        # was issued revoked it, even though it was never redeemed.
        if (
            claim is None
            or claim.expires_at <= time.time()
            or not still_matches(user, claim.session)
        ):
            await self._shutdown(AUTH_FAILED)
            return
        self.user_id = user.pk
        self._session = claim.session
        self._slot = await admission.acquire_slot(self.user_id, self.channel_name)
        if await self._abandoned():
            return
        if self._slot is None:
            await self._shutdown(TOO_MANY_CONNECTIONS)
            return
        self._joined = True
        await self.channel_layer.group_add(user_group(self.user_id), self.channel_name)
        if await self._abandoned():
            return
        # A revocation published before group_add finished went to an empty group; look again.
        valid = still_matches(await _load_user(self.user_id), self._session)
        if await self._abandoned():
            return
        if not valid:
            await self._shutdown(AUTH_FAILED)
            return
        self._auth_deadline.cancel()
        self._leave_pending()
        # No longer than the access token that bought the ticket (it may outlive a logout).
        self._token_expiry = asyncio.get_running_loop().call_later(
            max(0.0, claim.expires_at - time.time()),
            lambda: asyncio.ensure_future(self._shutdown(TOKEN_EXPIRED)),
        )
        self._registered = True
        self._watchdog = asyncio.ensure_future(self._watch())
        await self.send_json({"type": "ready"})

    async def _abandoned(self) -> bool:
        """True (after releasing anything acquired) when the socket closed during an await."""
        if self._closed:
            await self._leave()
        return self._closed

    async def _watch(self) -> None:
        """Re-check the user on a server-side timer; the client's pings are not trusted for it."""
        while not self._closed:
            await asyncio.sleep(settings.REALTIME_REVALIDATE_INTERVAL)
            if self._closed or not await self._still_valid():
                return
            slot = self._slot
            try:
                # Keep the connection slot from expiring while the socket is alive.
                kept = await admission.refresh_slot(slot, self.channel_name)
                if kept:
                    # Re-joining refreshes the membership before the layer's group expiry drops it.
                    await self.channel_layer.group_add(user_group(self.user_id), self.channel_name)
            except Exception:
                logger.warning("Realtime refresh for user %s failed", self.user_id, exc_info=True)
                await self._shutdown(INTERNAL_ERROR)
                return
            if self._closed:
                # Closed while refreshing: the refresh may have re-taken a slot _leave freed.
                await admission.release_slot(slot, self.channel_name)
                return
            if not kept:
                await self._shutdown(TOO_MANY_CONNECTIONS)
                return

    async def _still_valid(self) -> bool:
        try:
            user = await _load_user(self.user_id)
        except Exception:
            logger.warning("Realtime revalidation of user %s failed", self.user_id, exc_info=True)
            await self._shutdown(INTERNAL_ERROR)
            return False
        if self._closed:
            return False
        if not still_matches(user, self._session):
            await self._shutdown(SESSION_REVOKED)
            return False
        return True

    def _leave_pending(self) -> None:
        if self._pending:
            self._pending = False
            admission.leave_pending()

    def _stop_timers(self) -> None:
        if self._auth_deadline is not None:
            self._auth_deadline.cancel()
        if self._token_expiry is not None:
            self._token_expiry.cancel()
        self._leave_pending()
        watchdog, self._watchdog = self._watchdog, None
        # The watchdog may be the caller; it stops on its own once _closed is set.
        if watchdog is not None and watchdog is not asyncio.current_task():
            watchdog.cancel()

    async def _leave(self) -> None:
        """Release everything the socket holds; safe to call any number of times.

        Bounded by REALTIME_CLEANUP_TIMEOUT and never raises: a stalled or failing Redis must not
        keep the socket (or the consumer) alive. Whatever is not released lapses on its own: the
        slot after REALTIME_SLOT_TTL, the group membership with the channel layer's group expiry.
        """
        self._stop_timers()
        try:
            await asyncio.wait_for(self._release(), settings.REALTIME_CLEANUP_TIMEOUT)
        except TimeoutError:
            logger.warning("Realtime cleanup for user %s timed out", self.user_id)

    async def _release(self) -> None:
        if self._joined:
            # Not reset: an in-flight group_add can land after this discard, and the next _leave
            # (after that await) must discard again. Discarding twice is harmless.
            try:
                await self.channel_layer.group_discard(user_group(self.user_id), self.channel_name)
            except Exception:
                logger.warning("Realtime group discard failed", exc_info=True)
        slot, self._slot = self._slot, None
        if slot is not None:
            try:
                await admission.release_slot(slot, self.channel_name)
            except Exception:
                logger.warning("Realtime slot release failed", exc_info=True)

    async def _shutdown(self, code: int) -> None:
        if self._closed:
            return
        self._closed = True
        self._stop_timers()
        try:
            # The close frame goes out first, whatever happens to the cleanup.
            await self.close(code=code)
        finally:
            await self._leave()

    # ─── Channel layer handlers ────────────────────────────────

    async def realtime_event(self, message):
        # Checked before every event: a lost revocation must not leave the stream flowing.
        if self._registered and not self._closed and await self._still_valid():
            await self.send_json(message["event"])

    async def session_revoked(self, message):
        await self._shutdown(SESSION_REVOKED)

"""One-time socket tickets.

A ticket proves a JWT-authenticated user asked for a socket in the last few seconds, without the
JWT ever travelling over the socket or in a URL. Only its SHA-256 is stored, so a cache dump
cannot be replayed. It is bound to the user's session state at issue time (see sessions.py): a
password change or logout between issue and redemption makes it worthless. It also records when
the access token that bought it expires: the socket closes then, so a token that outlives its
logout cannot keep a stream open beyond its own lifetime.
"""

import hashlib
import secrets
import time
from dataclasses import asdict, dataclass

from django.conf import settings
from django.core.cache import cache

from .sessions import SessionState, session_of

_KEY_PREFIX = "realtime:ticket:"
# token_urlsafe(32) is 43 characters; anything far off that is not one of ours.
_MIN_LENGTH, _MAX_LENGTH = 32, 64


def _key(ticket: str) -> str:
    return _KEY_PREFIX + hashlib.sha256(ticket.encode()).hexdigest()


@dataclass(frozen=True)
class TicketClaim:
    user_id: int
    fingerprint: str
    generation: int
    # Unix time the buying access token expires.
    expires_at: float

    @property
    def session(self) -> SessionState:
        return SessionState(self.fingerprint, self.generation)


def issue_ticket(user, *, expires_at: float | None = None) -> str:
    """`expires_at`: the access token's exp; defaults to a fresh token's (no token at hand)."""
    if expires_at is None:
        expires_at = time.time() + settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds()
    ticket = secrets.token_urlsafe(32)
    claim = {"user_id": user.pk, **asdict(session_of(user)), "expires_at": expires_at}
    cache.set(_key(ticket), claim, timeout=settings.REALTIME_TICKET_TTL)
    return ticket


async def aconsume_ticket(ticket) -> TicketClaim | None:
    """Return the ticket's claim once; None for unknown, expired or already used tickets."""
    if not isinstance(ticket, str) or not _MIN_LENGTH <= len(ticket) <= _MAX_LENGTH:
        return None
    key = _key(ticket)
    stored = await cache.aget(key)
    # Delete is the atomic step: of two racing sockets only one sees True.
    if not isinstance(stored, dict) or not await cache.adelete(key):
        return None
    try:
        return TicketClaim(**stored)
    except TypeError:
        return None  # Issued by an older release with a different shape.

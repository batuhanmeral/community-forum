"""What ties a socket to the login that opened it.

A ticket records the user's session state when it is issued; the socket is valid only while the
user still has that state. Anything that ends sessions changes it: a password change, reset or
account deletion changes the password fingerprint, a logout bumps the realtime generation. So a
ticket issued earlier cannot be redeemed afterwards, and an open socket notices on its next check
even if the revocation event was lost.
"""

from dataclasses import dataclass

from rest_framework_simplejwt.utils import get_md5_hash_password

# The columns session_of() and still_matches() need; sockets load nothing else.
USER_FIELDS = ("id", "is_active", "password", "realtime_generation")


@dataclass(frozen=True)
class SessionState:
    fingerprint: str
    generation: int


def session_of(user) -> SessionState:
    # Same password claim CHECK_REVOKE_TOKEN puts in JWTs: it changes with every password change.
    return SessionState(get_md5_hash_password(user.password), user.realtime_generation)


def still_matches(user, session: SessionState) -> bool:
    """True while `user` is active and still has the session state a ticket/socket was bound to."""
    return user is not None and user.is_active and session_of(user) == session

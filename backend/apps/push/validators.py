"""Validation of what a browser hands us: the push endpoint (SSRF guard) and its keys."""

import base64
import binascii
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.asymmetric import ec

MAX_ENDPOINT_LENGTH = 500

# Push services the major browsers use. The server POSTs to whatever endpoint is stored, so an
# unrestricted one would let any user aim requests at internal hosts. Exact host or a subdomain.
ALLOWED_HOSTS = (
    "fcm.googleapis.com",  # Chrome, Edge, Opera, Brave (FCM)
    "push.services.mozilla.com",  # Firefox (autopush: updates.push.services.mozilla.com)
    "notify.windows.com",  # WNS
    "push.apple.com",  # Safari (web.push.apple.com)
)


def validate_endpoint(endpoint: str) -> str:
    if not isinstance(endpoint, str) or not endpoint or len(endpoint) > MAX_ENDPOINT_LENGTH:
        raise ValueError("Invalid push endpoint.")
    # Control characters, spaces and backslashes are how URL parsers get confused.
    if any(ord(ch) <= 32 or ord(ch) == 127 or ch == "\\" for ch in endpoint):
        raise ValueError("Invalid push endpoint.")
    parts = urlsplit(endpoint)
    host = (parts.hostname or "").lower()
    if (
        parts.scheme != "https"
        or not host
        or not host.isascii()
        or "@" in parts.netloc
        or parts.username
        or parts.password
        or parts.fragment
        or parts.port not in (None, 443)
        or parts.path in ("", "/")
    ):
        raise ValueError("Push endpoints must be https URLs of a known push service.")
    if not any(host == allowed or host.endswith("." + allowed) for allowed in ALLOWED_HOSTS):
        raise ValueError("Push endpoints must be https URLs of a known push service.")
    return endpoint


def _decode(value: str, label: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError(f"Missing {label}.")
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"Invalid {label}.") from exc


def validate_keys(p256dh: str, auth: str) -> tuple[str, str]:
    """Check the browser's ECDH public key (a real P-256 point) and 16-byte auth secret."""
    point = _decode(p256dh, "p256dh")
    secret = _decode(auth, "auth")
    if len(point) != 65 or point[0] != 4 or len(secret) != 16:
        raise ValueError("Invalid subscription keys.")
    try:
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), point)
    except ValueError as exc:
        raise ValueError("Invalid subscription keys.") from exc
    return p256dh.rstrip("="), auth.rstrip("=")

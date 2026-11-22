"""VAPID key handling. Keys come from the environment; without a consistent set the feature is off."""

import base64
import functools

from cryptography.hazmat.primitives import serialization
from django.conf import settings
from py_vapid import Vapid


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def generate_keys() -> tuple[str, str]:
    """A new (private, public) pair, both URL-safe base64: the private key is the raw 32 bytes,
    the public key the uncompressed point browsers expect as applicationServerKey."""
    vapid = Vapid()
    vapid.generate_keys()
    private = vapid.private_key.private_numbers().private_value.to_bytes(32, "big")
    public = vapid.public_key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return _b64(private), _b64(public)


@functools.lru_cache(maxsize=4)
def _consistent(private: str, public: str, subject: str) -> bool:
    if not (private and public) or not subject.startswith(("mailto:", "https://")):
        return False
    try:
        vapid = Vapid.from_string(private)
        derived = _b64(
            vapid.public_key.public_bytes(
                serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
            )
        )
    except Exception:  # malformed key material: treat as "not configured"
        return False
    return derived == public.rstrip("=")


def push_enabled() -> bool:
    return _consistent(
        settings.VAPID_PRIVATE_KEY, settings.VAPID_PUBLIC_KEY, settings.VAPID_SUBJECT
    )


def reset_cache() -> None:
    _consistent.cache_clear()

"""Settings helpers for the realtime (WebSocket) service; pure functions so they can be unit-tested."""

from urllib.parse import urlsplit, urlunsplit


def channel_layers(redis_url: str, *, db: int) -> dict:
    """Redis channel layer on its own db index; empty (realtime off) without a Redis URL."""
    if not redis_url:
        return {}
    address = urlunsplit(urlsplit(redis_url)._replace(path=f"/{db}"))
    return {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                # Consumers block in BZPOPMIN for 5 s; redis-py 8's default 5 s socket timeout
                # would cut that read short and crash every idle socket.
                "hosts": [{"address": address, "socket_timeout": 15}],
                "prefix": "nexus:realtime",
                # Events are wake-up signals; a stale one is worthless, a lost one is resynced.
                "expiry": 30,
                "capacity": 100,
            },
        }
    }


def websocket_origins(frontend_url: str, trusted_origins) -> list[str]:
    """Origins allowed to open a socket: the SPA's own origin plus any CSRF-trusted origin."""
    parts = urlsplit(frontend_url)
    candidates = [f"{parts.scheme}://{parts.netloc}", *(o.strip() for o in trusted_origins)]
    origins: list[str] = []
    for origin in candidates:
        if origin and origin not in origins:
            origins.append(origin)
    return origins

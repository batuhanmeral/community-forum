"""Admission limits for realtime sockets.

- Unauthenticated sockets: at most REALTIME_MAX_PENDING_SOCKETS per process are waiting for their
  auth frame; further handshakes are refused. A single event loop serves the process, so a plain
  counter is atomic. (nginx caps sockets per client address and in total in front of this.)
- Authenticated sockets: at most REALTIME_MAX_SOCKETS_PER_USER per user across every realtime
  process. Each socket holds one of the user's numbered slots, owned by its channel name. A slot
  expires after REALTIME_SLOT_TTL unless its socket's server-side timer refreshes it, so a crashed
  process cannot lock a user out for longer than that.

Every slot operation is a single atomic step that checks the owner: in Redis, SET NX for taking a
slot and a Lua script for refreshing and releasing it. A socket whose slot lapsed and was retaken
by another can therefore never extend or delete the newcomer's slot. Without Redis
(REALTIME_SLOT_REDIS_URL empty: tests, or realtime off) the slots live in this process under a
lock, which is exact because there is only one realtime process then.
"""

import asyncio
import threading
import time
import weakref

from django.conf import settings
from redis.asyncio import Redis

SLOT_PREFIX = "nexus:realtime:slot:"
_pending = 0


def enter_pending() -> bool:
    """Take a place for an unauthenticated socket; False when the process is full."""
    global _pending
    if _pending >= settings.REALTIME_MAX_PENDING_SOCKETS:
        return False
    _pending += 1
    return True


def leave_pending() -> None:
    global _pending
    _pending = max(0, _pending - 1)


def pending_sockets() -> int:
    return _pending


def _slot_key(user_id: int, index: int) -> str:
    return f"{SLOT_PREFIX}{user_id}:{index}"


async def acquire_slot(user_id: int, owner: str) -> str | None:
    """Take a free connection slot of the user for `owner`; None when all are held."""
    for index in range(settings.REALTIME_MAX_SOCKETS_PER_USER):
        key = _slot_key(user_id, index)
        if await _store().take(key, owner, settings.REALTIME_SLOT_TTL):
            return key
    return None


async def refresh_slot(key: str, owner: str) -> bool:
    """Extend `owner`'s slot; take it back if it lapsed. False when someone else holds it now."""
    return await _store().refresh(key, owner, settings.REALTIME_SLOT_TTL)


async def release_slot(key: str, owner: str) -> None:
    """Free the slot if `owner` still holds it; a slot retaken by another socket is left alone."""
    await _store().release(key, owner)


def _store():
    return _RedisSlots if settings.REALTIME_SLOT_REDIS_URL else _MemorySlots


# ─── Redis ─────────────────────────────────────────────────

# KEYS[1] = slot, ARGV[1] = owner, ARGV[2] = TTL in milliseconds.
_REFRESH = """
local holder = redis.call('GET', KEYS[1])
if holder == ARGV[1] then
  return redis.call('PEXPIRE', KEYS[1], ARGV[2])
end
if not holder then
  redis.call('SET', KEYS[1], ARGV[1], 'PX', ARGV[2])
  return 1
end
return 0
"""
_RELEASE = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
end
return 0
"""

# redis.asyncio connections belong to the event loop that opened them (uvicorn has one; tests
# start a new loop per scenario), so keep one client per loop.
_clients: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, tuple[str, Redis]]" = (
    weakref.WeakKeyDictionary()
)


def _redis_client() -> Redis:
    loop = asyncio.get_running_loop()
    url = settings.REALTIME_SLOT_REDIS_URL
    cached = _clients.get(loop)
    if cached is None or cached[0] != url:
        cached = (url, Redis.from_url(url, socket_timeout=5, socket_connect_timeout=5))
        _clients[loop] = cached
    return cached[1]


def _ms(seconds: float) -> int:
    return max(1, int(seconds * 1000))


class _RedisSlots:
    @staticmethod
    async def take(key: str, owner: str, ttl: float) -> bool:
        return bool(await _redis_client().set(key, owner, nx=True, px=_ms(ttl)))

    @staticmethod
    async def refresh(key: str, owner: str, ttl: float) -> bool:
        return bool(await _redis_client().eval(_REFRESH, 1, key, owner, _ms(ttl)))

    @staticmethod
    async def release(key: str, owner: str) -> None:
        await _redis_client().eval(_RELEASE, 1, key, owner)


# ─── In-process ────────────────────────────────────────────

_memory: dict[str, tuple[str, float]] = {}
_memory_lock = threading.Lock()


def _holder(key: str) -> str | None:
    entry = _memory.get(key)
    if entry is None or entry[1] <= time.monotonic():
        return None
    return entry[0]


class _MemorySlots:
    @staticmethod
    async def take(key: str, owner: str, ttl: float) -> bool:
        with _memory_lock:
            if _holder(key) is not None:
                return False
            _memory[key] = (owner, time.monotonic() + ttl)
            return True

    @staticmethod
    async def refresh(key: str, owner: str, ttl: float) -> bool:
        with _memory_lock:
            if _holder(key) not in (owner, None):
                return False
            _memory[key] = (owner, time.monotonic() + ttl)
            return True

    @staticmethod
    async def release(key: str, owner: str) -> None:
        with _memory_lock:
            if _holder(key) == owner:
                del _memory[key]

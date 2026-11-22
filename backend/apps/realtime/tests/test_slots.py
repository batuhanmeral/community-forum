"""Per-user connection slots, against both stores: in-process (no Redis) and Redis.

The Redis variant needs REALTIME_TEST_REDIS_URL (CI provides one); it is skipped without it.
"""

import asyncio
import itertools
import os

import pytest
from asgiref.sync import async_to_sync

from apps.realtime import admission

REDIS_URL = os.environ.get("REALTIME_TEST_REDIS_URL", "")
_user_ids = itertools.count(900_000)


def run(coro_fn):
    return async_to_sync(coro_fn)()


@pytest.fixture(params=["memory", "redis"])
def store(request, settings):
    if request.param == "redis":
        if not REDIS_URL:
            pytest.skip("REALTIME_TEST_REDIS_URL is not set")
        settings.REALTIME_SLOT_REDIS_URL = REDIS_URL
    else:
        settings.REALTIME_SLOT_REDIS_URL = ""
    yield request.param
    if request.param == "redis":
        import redis

        client = redis.Redis.from_url(REDIS_URL)
        keys = list(client.scan_iter(f"{admission.SLOT_PREFIX}*"))
        if keys:
            client.delete(*keys)
        client.close()


@pytest.fixture
def user_id():
    return next(_user_ids)


def test_slots_are_capped_per_user(store, user_id, settings):
    settings.REALTIME_MAX_SOCKETS_PER_USER = 2

    async def scenario():
        first = await admission.acquire_slot(user_id, "a")
        second = await admission.acquire_slot(user_id, "b")
        third = await admission.acquire_slot(user_id, "c")
        await admission.release_slot(first, "a")
        fourth = await admission.acquire_slot(user_id, "d")
        return first, second, third, fourth

    first, second, third, fourth = run(scenario)
    assert None not in (first, second) and first != second
    assert third is None
    assert fourth == first


def test_slot_is_only_released_and_refreshed_by_its_owner(store, user_id):
    async def scenario():
        key = await admission.acquire_slot(user_id, "owner")
        await admission.release_slot(key, "someone-else")
        kept = await admission.refresh_slot(key, "owner")
        stolen = await admission.refresh_slot(key, "someone-else")
        await admission.release_slot(key, "owner")
        reacquired = await admission.refresh_slot(key, "newcomer")
        return kept, stolen, reacquired

    # A slot that expired (or was evicted) is simply taken again by its next refresher.
    assert run(scenario) == (True, False, True)


def test_late_owner_cannot_touch_a_slot_retaken_after_expiry(store, user_id, settings):
    """A's slot lapses and B takes it; A's late release/refresh must leave B's slot alone."""
    settings.REALTIME_MAX_SOCKETS_PER_USER = 1
    settings.REALTIME_SLOT_TTL = 0.1

    async def scenario():
        key = await admission.acquire_slot(user_id, "A")
        await asyncio.sleep(0.2)
        assert await admission.acquire_slot(user_id, "B") == key
        settings.REALTIME_SLOT_TTL = 5
        await admission.release_slot(key, "A")
        refreshed_by_a = await admission.refresh_slot(key, "A")
        # B still holds it: nobody else gets in, and B can keep it.
        blocked = await admission.acquire_slot(user_id, "C")
        kept_by_b = await admission.refresh_slot(key, "B")
        return refreshed_by_a, blocked, kept_by_b

    assert run(scenario) == (False, None, True)


def test_slots_expire(store, user_id, settings):
    settings.REALTIME_MAX_SOCKETS_PER_USER = 1
    settings.REALTIME_SLOT_TTL = 0.1

    async def scenario():
        await admission.acquire_slot(user_id, "dead")
        blocked = await admission.acquire_slot(user_id, "next")
        await asyncio.sleep(0.2)
        return blocked, await admission.acquire_slot(user_id, "next")

    blocked, later = run(scenario)
    assert blocked is None and later is not None


def test_redis_compare_and_act_is_one_atomic_command(store, user_id, monkeypatch):
    """Release and refresh never read and then write in two round trips."""
    if store != "redis":
        pytest.skip("Redis only")
    calls = []
    real_client = admission._redis_client

    class Spy:
        def __init__(self, client):
            self._client = client

        def __getattr__(self, name):
            calls.append(name)
            return getattr(self._client, name)

    monkeypatch.setattr(admission, "_redis_client", lambda: Spy(real_client()))

    async def scenario():
        key = await admission.acquire_slot(user_id, "owner")
        calls.clear()
        await admission.refresh_slot(key, "owner")
        refresh_calls = list(calls)
        calls.clear()
        await admission.release_slot(key, "owner")
        return refresh_calls, list(calls)

    assert run(scenario) == (["eval"], ["eval"])


@pytest.mark.django_db(transaction=True)
def test_sockets_use_the_store(store, settings, django_user_model):
    from apps.realtime.consumers import TOO_MANY_CONNECTIONS
    from apps.realtime.tests.test_admission import try_auth
    from apps.realtime.tests.test_consumer import authed

    settings.REALTIME_MAX_SOCKETS_PER_USER = 1
    alice = django_user_model.objects.create_user(username="alice", password="x")

    async def scenario():
        ws = await authed(alice)
        refused = await try_auth(alice)
        await ws.disconnect()  # releases the slot in the store
        state, again = await try_auth(alice)
        await again.disconnect()
        return refused, state

    assert run(scenario) == (("closed", TOO_MANY_CONNECTIONS), "ready")

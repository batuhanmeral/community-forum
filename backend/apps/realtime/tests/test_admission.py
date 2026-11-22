import asyncio

import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model

from apps.realtime import admission
from apps.realtime.consumers import AUTH_FAILED, TOO_MANY_CONNECTIONS
from apps.realtime.tests.test_consumer import authed, client, send_to
from apps.realtime.tickets import issue_ticket

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


def run(coro_fn):
    return async_to_sync(coro_fn)()


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="alice", email="a@x.com", password="x")


async def try_auth(user):
    """Open and authenticate a socket; ("ready", ws) or ("closed", code)."""
    ws = client()
    connected, code = await ws.connect()
    if not connected:
        return "refused", code
    await ws.send_json({"type": "auth", "ticket": issue_ticket(user)})
    output = await ws.receive_output(1)
    if output["type"] == "websocket.close":
        return "closed", output["code"]
    return "ready", ws


# ─── Unauthenticated sockets ─────────────────────────────


def test_unauthenticated_sockets_are_capped(settings):
    settings.REALTIME_MAX_PENDING_SOCKETS = 2

    async def scenario():
        first, second, third = client(), client(), client()
        results = [await first.connect(), await second.connect(), await third.connect()]
        await first.disconnect()
        await second.disconnect()
        return results

    accepted, accepted_too, refused = run(scenario)
    assert accepted[0] and accepted_too[0]
    assert refused[0] is False


def test_pending_place_is_freed_by_auth_failure_timeout_and_success(alice, settings):
    settings.REALTIME_MAX_PENDING_SOCKETS = 1
    settings.REALTIME_AUTH_TIMEOUT = 0.05

    async def scenario():
        failed = client()
        assert (await failed.connect())[0]
        await failed.send_json({"type": "auth", "ticket": "A" * 43})
        assert await failed.receive_close() == AUTH_FAILED

        silent = client()
        assert (await silent.connect())[0]
        assert await silent.receive_close(timeout=2) == AUTH_FAILED

        ws = await authed(alice)  # takes the place, then leaves it on registration
        again = client()
        accepted = (await again.connect())[0]
        await again.disconnect()
        await ws.disconnect()
        return accepted, admission.pending_sockets()

    assert run(scenario) == (True, 0)


# ─── Per-user limit ──────────────────────────────────────


def test_per_user_connection_limit(alice, settings):
    settings.REALTIME_MAX_SOCKETS_PER_USER = 2

    async def scenario():
        one = await authed(alice)
        two = await authed(alice)
        state, code = await try_auth(alice)
        await one.disconnect()  # releases its slot
        state_after, three = await try_auth(alice)
        await two.disconnect()
        await three.disconnect()
        return state, code, state_after

    assert run(scenario) == ("closed", TOO_MANY_CONNECTIONS, "ready")


def test_revoked_socket_releases_its_slot(alice, settings):
    settings.REALTIME_MAX_SOCKETS_PER_USER = 1

    async def scenario():
        ws = await authed(alice)
        await send_to(alice, {"type": "session.revoked"})
        await ws.receive_close()
        state, again = await try_auth(alice)
        await again.disconnect()
        return state

    assert run(scenario) == "ready"


def test_slots_of_a_crashed_process_expire(alice, settings):
    settings.REALTIME_MAX_SOCKETS_PER_USER = 1
    settings.REALTIME_SLOT_TTL = 0.2

    async def scenario():
        # A process died holding the user's only slot: it never released it.
        assert await admission.acquire_slot(alice.pk, "dead-process!channel") is not None
        blocked = await try_auth(alice)
        await asyncio.sleep(0.3)
        state, ws = await try_auth(alice)
        await ws.disconnect()
        return blocked, state

    assert run(scenario) == (("closed", TOO_MANY_CONNECTIONS), "ready")


def test_open_sockets_keep_their_slot_alive(alice, settings):
    settings.REALTIME_MAX_SOCKETS_PER_USER = 1
    settings.REALTIME_SLOT_TTL = 0.2
    settings.REALTIME_REVALIDATE_INTERVAL = 0.05

    async def scenario():
        ws = await authed(alice)
        await asyncio.sleep(0.5)  # well past the TTL: the server's timer must have refreshed it
        result = await try_auth(alice)
        await ws.disconnect()
        return result

    assert run(scenario) == ("closed", TOO_MANY_CONNECTIONS)


def test_failed_ticket_lookup_closes_cleanly(alice, monkeypatch):
    import apps.realtime.consumers as consumers

    async def broken(ticket):
        raise ConnectionError("redis is down")

    monkeypatch.setattr(consumers, "aconsume_ticket", broken)

    async def scenario():
        ws = client()
        await ws.connect()
        await ws.send_json({"type": "auth", "ticket": issue_ticket(alice)})
        code = await ws.receive_close()
        await ws.disconnect()
        return code, admission.pending_sockets()

    assert run(scenario) == (consumers.INTERNAL_ERROR, 0)


def test_crashed_consumer_returns_its_pending_place(monkeypatch):
    from apps.realtime.consumers import StreamConsumer

    def crash(text_data):
        raise RuntimeError("bug")

    monkeypatch.setattr(StreamConsumer, "_parse", staticmethod(crash))

    async def scenario():
        ws = client()
        await ws.connect()
        await ws.send_text("{}")
        # The crash surfaces; no timer of the dead consumer writes to the socket afterwards.
        with pytest.raises(RuntimeError):
            await ws.receive_output(1)
        return admission.pending_sockets()

    assert run(scenario) == 0


def test_deadline_during_subscription_leaves_no_membership(alice, settings, monkeypatch):
    """The deadline's cleanup can run before an in-flight group_add lands; discard again after."""
    from channels.layers import get_channel_layer

    from apps.realtime.groups import user_group

    settings.REALTIME_AUTH_TIMEOUT = 0.1
    layer = get_channel_layer()
    real_group_add = layer.group_add

    async def slow_group_add(group, channel):
        await asyncio.sleep(0.3)
        await real_group_add(group, channel)

    monkeypatch.setattr(layer, "group_add", slow_group_add)

    async def scenario():
        ws = client()
        await ws.connect()
        await ws.send_json({"type": "auth", "ticket": issue_ticket(alice)})
        code = await ws.receive_close(timeout=0.3)
        await asyncio.sleep(0.4)
        await ws.disconnect()
        return code, layer.groups.get(user_group(alice.pk), {}), admission.pending_sockets()

    assert run(scenario) == (AUTH_FAILED, {}, 0)


def test_socket_whose_slot_was_taken_over_is_closed(alice, settings):
    """A slot that lapsed (stall, eviction) and went to another socket is not shared."""
    settings.REALTIME_MAX_SOCKETS_PER_USER = 1
    settings.REALTIME_SLOT_TTL = 0.1
    settings.REALTIME_REVALIDATE_INTERVAL = 0.4  # the refresh comes too late

    async def scenario():
        ws = await authed(alice)
        await asyncio.sleep(0.2)
        settings.REALTIME_SLOT_TTL = 5  # the newcomer keeps it
        assert await admission.acquire_slot(alice.pk, "another-socket") is not None
        return await ws.receive_close(timeout=2)

    assert run(scenario) == TOO_MANY_CONNECTIONS


def test_slot_refresh_failure_closes_the_socket(alice, settings, monkeypatch):
    import apps.realtime.consumers as consumers

    settings.REALTIME_REVALIDATE_INTERVAL = 0.05

    async def broken(key, owner):
        raise ConnectionError("redis is down")

    async def scenario():
        ws = await authed(alice)
        monkeypatch.setattr(admission, "refresh_slot", broken)
        return await ws.receive_close(timeout=2)

    assert run(scenario) == consumers.INTERNAL_ERROR

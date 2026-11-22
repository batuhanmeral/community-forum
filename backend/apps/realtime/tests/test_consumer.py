import asyncio

import pytest
from asgiref.sync import async_to_sync, sync_to_async
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model

from apps.realtime.consumers import AUTH_FAILED, SESSION_REVOKED
from apps.realtime.groups import user_group
from apps.realtime.tests.communicator import WebsocketClient
from apps.realtime.tickets import issue_ticket

User = get_user_model()
STREAM = "/ws/v1/stream/"

# The consumer reaches the DB from a worker thread, which needs committed rows.
pytestmark = pytest.mark.django_db(transaction=True)


def run(coro_fn):
    return async_to_sync(coro_fn)()


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="alice", email="a@x.com", password="x")


@pytest.fixture
def bob(db):
    return User.objects.create_user(username="bob", email="b@x.com", password="x")


def client():
    from config.asgi import application

    return WebsocketClient(application, STREAM)


async def authed(user):
    ws = client()
    connected, _ = await ws.connect()
    assert connected
    await ws.send_json({"type": "auth", "ticket": issue_ticket(user)})
    assert await ws.receive_json() == {"type": "ready"}
    return ws


async def send_to(user, message):
    await get_channel_layer().group_send(user_group(user.pk), message)


def event(payload):
    return {"type": "realtime.event", "event": payload}


def test_valid_ticket_connects_and_receives_events(alice):
    async def scenario():
        ws = await authed(alice)
        await send_to(alice, event({"type": "message.created", "conversation_id": 7}))
        received = await ws.receive_json()
        await ws.disconnect()
        return received

    assert run(scenario) == {"type": "message.created", "conversation_id": 7}


@pytest.mark.parametrize(
    "first_message",
    [
        {"type": "auth", "ticket": "A" * 43},
        {"type": "auth"},
        {"type": "ping"},
        ["auth"],
        "not json",
        "x" * 5000,
    ],
)
def test_bad_first_message_closes_with_auth_failed(first_message):
    async def scenario():
        ws = client()
        assert (await ws.connect())[0]
        if isinstance(first_message, str):
            await ws.send_text(first_message)
        else:
            await ws.send_json(first_message)
        return await ws.receive_close()

    assert run(scenario) == AUTH_FAILED


def test_reused_ticket_is_rejected(alice):
    ticket = issue_ticket(alice)

    async def scenario():
        first = client()
        await first.connect()
        await first.send_json({"type": "auth", "ticket": ticket})
        assert await first.receive_json() == {"type": "ready"}
        second = client()
        await second.connect()
        await second.send_json({"type": "auth", "ticket": ticket})
        code = await second.receive_close()
        await first.disconnect()
        return code

    assert run(scenario) == AUTH_FAILED


def test_expired_ticket_is_rejected(alice):
    from django.core.cache import cache

    ticket = issue_ticket(alice)
    cache.clear()  # what the TTL does

    async def scenario():
        ws = client()
        await ws.connect()
        await ws.send_json({"type": "auth", "ticket": ticket})
        return await ws.receive_close()

    assert run(scenario) == AUTH_FAILED


def test_missing_auth_times_out(settings):
    settings.REALTIME_AUTH_TIMEOUT = 0.05

    async def scenario():
        ws = client()
        assert (await ws.connect())[0]
        return await ws.receive_close(timeout=2)

    assert run(scenario) == AUTH_FAILED


def test_inactive_user_is_rejected(alice):
    ticket = issue_ticket(alice)
    User.objects.filter(pk=alice.pk).update(is_active=False)

    async def scenario():
        ws = client()
        await ws.connect()
        await ws.send_json({"type": "auth", "ticket": ticket})
        return await ws.receive_close()

    assert run(scenario) == AUTH_FAILED


def test_socket_is_refused_without_channel_layer(settings):
    settings.CHANNEL_LAYERS = {}

    async def scenario():
        return await client().connect()

    assert run(scenario) == (False, 1000)


def test_user_only_receives_own_events(alice, bob):
    async def scenario():
        ws = await authed(alice)
        # Clients cannot pick their groups; unknown requests are ignored.
        await ws.send_json({"type": "subscribe", "group": user_group(bob.pk)})
        await send_to(bob, event({"type": "notification.created"}))
        nothing = await ws.receive_nothing(timeout=0.2)
        await ws.disconnect()
        return nothing

    assert run(scenario) is True


def test_session_revoked_closes_socket(alice):
    async def scenario():
        ws = await authed(alice)
        await send_to(alice, {"type": "session.revoked"})
        return await ws.receive_close()

    assert run(scenario) == SESSION_REVOKED


def test_ping_gets_pong(alice):
    async def scenario():
        ws = await authed(alice)
        await ws.send_json({"type": "ping"})
        reply = await ws.receive_json()
        await ws.disconnect()
        return reply

    assert run(scenario) == {"type": "pong"}


def test_server_revalidates_password_change_without_pings(alice, settings):
    settings.REALTIME_REVALIDATE_INTERVAL = 0.05

    async def scenario():
        ws = await authed(alice)
        # The client never pings: the server's own timer must notice.
        await asyncio.to_thread(change_password, alice.pk)
        return await ws.receive_close(timeout=2)

    assert run(scenario) == SESSION_REVOKED


def test_server_revalidates_deactivation_without_pings(alice, settings):
    settings.REALTIME_REVALIDATE_INTERVAL = 0.05

    async def scenario():
        ws = await authed(alice)
        await asyncio.to_thread(lambda: User.objects.filter(pk=alice.pk).update(is_active=False))
        return await ws.receive_close(timeout=2)

    assert run(scenario) == SESSION_REVOKED


def test_logout_closes_a_socket_that_missed_the_event(alice, settings, monkeypatch):
    settings.REALTIME_REVALIDATE_INTERVAL = 0.05
    # Redis evicted or dropped the session.revoked message.
    monkeypatch.setattr("apps.realtime.publish._send", lambda user_id, message: None)

    async def scenario():
        ws = await authed(alice)
        await sync_to_async(log_in_and_out)("alice")
        return await ws.receive_close(timeout=2)

    assert run(scenario) == SESSION_REVOKED


def test_events_are_not_forwarded_after_deactivation(alice):
    """Checked before every event, not only on the (slow) timer."""

    async def scenario():
        ws = await authed(alice)
        await asyncio.to_thread(lambda: User.objects.filter(pk=alice.pk).update(is_active=False))
        await send_to(alice, event({"type": "notification.created"}))
        return await ws.receive_output(1)

    output = run(scenario)
    assert output["type"] == "websocket.close"
    assert output["code"] == SESSION_REVOKED


def test_stalled_ticket_lookup_still_times_out(alice, settings, monkeypatch):
    """The auth deadline covers the whole handshake, not just the wait for the first frame."""
    import apps.realtime.consumers as consumers

    settings.REALTIME_AUTH_TIMEOUT = 0.1
    real_consume = consumers.aconsume_ticket

    async def slow_consume(ticket):
        claim = await real_consume(ticket)
        await asyncio.sleep(0.4)  # e.g. a Redis stall
        return claim

    monkeypatch.setattr(consumers, "aconsume_ticket", slow_consume)

    async def scenario():
        ws = client()
        await ws.connect()
        await ws.send_json({"type": "auth", "ticket": issue_ticket(alice)})
        code = await ws.receive_close(timeout=0.3)
        # Let the stalled lookup finish: it must not subscribe or say "ready" on a closed socket.
        await asyncio.sleep(0.6)
        quiet = await ws.receive_nothing(timeout=0.1)
        await ws.disconnect()
        return code, quiet, get_channel_layer().groups.get(user_group(alice.pk), {})

    assert run(scenario) == (AUTH_FAILED, True, {})


def test_events_stop_after_socket_closes(alice):
    async def scenario():
        ws = await authed(alice)
        await ws.disconnect()
        layer = get_channel_layer()
        return layer.groups.get(user_group(alice.pk), {})

    assert run(scenario) == {}


def change_password(user_id):
    user = User.objects.get(pk=user_id)
    user.set_password("another-password")
    # Bypass any publish hook: the socket must not depend on the revocation event.
    User.objects.filter(pk=user.pk).update(password=user.password)


def test_ticket_from_before_a_password_change_is_rejected(alice):
    ticket = issue_ticket(alice)
    change_password(alice.pk)

    async def scenario():
        ws = client()
        await ws.connect()
        await ws.send_json({"type": "auth", "ticket": ticket})
        code = await ws.receive_close()
        return code, get_channel_layer().groups.get(user_group(alice.pk), {})

    assert run(scenario) == (AUTH_FAILED, {})


def test_revocation_during_subscription_is_caught(alice, monkeypatch, settings):
    """A session.revoked published before group_add completes never reaches the socket."""
    # Generous deadline: the recheck itself must refuse the socket, not the auth timeout.
    settings.REALTIME_AUTH_TIMEOUT = 5
    layer = get_channel_layer()
    real_group_add = layer.group_add

    async def racing_group_add(group, channel):
        await asyncio.to_thread(change_password, alice.pk)
        await real_group_add(group, channel)

    monkeypatch.setattr(layer, "group_add", racing_group_add)

    async def scenario():
        ws = client()
        await ws.connect()
        await ws.send_json({"type": "auth", "ticket": issue_ticket(alice)})
        code = await ws.receive_close()
        return code, layer.groups.get(user_group(alice.pk), {})

    assert run(scenario) == (AUTH_FAILED, {})


def log_in_and_out(username, password="x"):
    """A full session on the REST API, ended through the logout endpoint."""
    from django.urls import reverse
    from rest_framework.test import APIClient

    api = APIClient()
    login = api.post(
        reverse("api_v1:auth:auth-login"),
        {"username": username, "password": password},
        format="json",
    )
    assert login.status_code == 200
    assert api.post(reverse("api_v1:auth:auth-logout")).status_code == 204


def test_logout_closes_a_retained_socket(alice):
    async def scenario():
        # Opened earlier and kept alive on its own (another tab, or a copied socket).
        ws = await authed(alice)
        await sync_to_async(log_in_and_out)("alice")
        return await ws.receive_close()

    assert run(scenario) == SESSION_REVOKED


def test_ticket_from_before_a_logout_is_rejected(alice):
    ticket = issue_ticket(alice)
    log_in_and_out("alice")

    async def scenario():
        ws = client()
        await ws.connect()
        await ws.send_json({"type": "auth", "ticket": ticket})
        return await ws.receive_close()

    assert run(scenario) == AUTH_FAILED


def test_revalidation_failure_closes_the_socket(alice, settings, monkeypatch):
    """If the user cannot be checked (database down), the socket fails closed."""
    import apps.realtime.consumers as consumers

    settings.REALTIME_REVALIDATE_INTERVAL = 0.05

    async def scenario():
        ws = await authed(alice)

        async def broken(user_id):
            raise RuntimeError("database is down")

        monkeypatch.setattr(consumers, "_load_user", broken)
        return await ws.receive_close(timeout=2)

    assert run(scenario) == consumers.INTERNAL_ERROR


def test_later_auth_frames_are_ignored(alice):
    async def scenario():
        ws = client()
        await ws.connect()
        await ws.send_json({"type": "auth", "ticket": issue_ticket(alice)})
        assert await ws.receive_json() == {"type": "ready"}
        await ws.send_json({"type": "auth", "ticket": issue_ticket(alice)})  # ignored
        await ws.send_json({"type": "ping"})
        reply = await ws.receive_json()
        await ws.disconnect()
        return reply

    assert run(scenario) == {"type": "pong"}


async def _stall(*args, **kwargs):
    await asyncio.sleep(5)


async def _explode(*args, **kwargs):
    raise ConnectionError("redis is down")


@pytest.mark.parametrize("behaviour", [_stall, _explode], ids=["stalled", "raising"])
@pytest.mark.parametrize("step", ["group_discard", "release_slot"])
def test_close_does_not_wait_for_cleanup(alice, settings, monkeypatch, step, behaviour):
    """The close frame goes out first; cleanup is bounded and cannot swallow it."""
    from apps.realtime import admission

    settings.REALTIME_CLEANUP_TIMEOUT = 0.2
    if step == "group_discard":
        monkeypatch.setattr(get_channel_layer(), "group_discard", behaviour)
    else:
        monkeypatch.setattr(admission, "release_slot", behaviour)

    async def scenario():
        ws = await authed(alice)
        await send_to(alice, {"type": "session.revoked"})
        code = await ws.receive_close(timeout=0.5)
        # A second revocation and the disconnect find nothing left to do and do not crash.
        await send_to(alice, {"type": "session.revoked"})
        await ws.disconnect()
        return code

    assert run(scenario) == SESSION_REVOKED


def test_socket_closes_when_its_access_token_expires(alice):
    """A logged-out device's still-valid access token buys at most its remaining lifetime."""
    from datetime import timedelta

    from django.urls import reverse
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import AccessToken

    from apps.realtime.consumers import TOKEN_EXPIRED

    token = AccessToken.for_user(alice)
    token.set_exp(lifetime=timedelta(seconds=2))
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    ticket = api.post(reverse("api_v1:realtime:realtime-ticket")).data["ticket"]

    async def scenario():
        ws = client()
        await ws.connect()
        await ws.send_json({"type": "auth", "ticket": ticket})
        assert await ws.receive_json() == {"type": "ready"}
        code = await ws.receive_close(timeout=4)
        await ws.disconnect()
        return code, get_channel_layer().groups.get(user_group(alice.pk), {})

    assert run(scenario) == (TOKEN_EXPIRED, {})


def test_ticket_of_an_expired_access_token_is_refused(alice):
    import time

    ticket = issue_ticket(alice, expires_at=time.time() - 1)

    async def scenario():
        ws = client()
        await ws.connect()
        await ws.send_json({"type": "auth", "ticket": ticket})
        return await ws.receive_close()

    assert run(scenario) == AUTH_FAILED

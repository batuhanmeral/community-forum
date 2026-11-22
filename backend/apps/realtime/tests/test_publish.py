import asyncio
import logging
import time

import pytest
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient

from apps.messaging.models import Conversation, Message
from apps.notifications.models import Notification
from apps.notifications.services import notify
from apps.realtime.groups import user_group
from apps.realtime.publish import publish_to_user, revoke_sessions
from apps.social.models import Block

User = get_user_model()
PW = "Old-Pass-123!"


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="alice", email="a@x.com", password=PW)


@pytest.fixture
def bob(db):
    return User.objects.create_user(username="bob", email="b@x.com", password=PW)


@pytest.fixture
def conv(alice, bob):
    a, b = sorted((alice, bob), key=lambda u: u.id)
    return Conversation.objects.create(participant_a=a, participant_b=b)


@pytest.fixture
def sent(monkeypatch):
    """Record what reaches the channel layer instead of delivering it."""
    calls = []
    layer = get_channel_layer()

    async def record(group, message):
        calls.append((group, message))

    monkeypatch.setattr(layer, "group_send", record)
    return calls


@pytest.fixture
def commit(django_capture_on_commit_callbacks):
    def run():
        return django_capture_on_commit_callbacks(execute=True)

    return run


def as_user(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def ev(user, payload):
    return (user_group(user.pk), {"type": "realtime.event", "event": payload})


def revoked(user):
    return (user_group(user.pk), {"type": "session.revoked"})


# ─── publish helpers ─────────────────────────────────────


@pytest.mark.django_db
def test_publish_waits_for_commit(alice, sent, commit):
    with commit():
        publish_to_user(alice.pk, {"type": "unread.changed"})
        assert sent == []
    assert sent == [ev(alice, {"type": "unread.changed"})]


@pytest.mark.django_db
def test_rolled_back_publish_is_dropped(alice, sent, commit):
    with commit() as callbacks:
        with pytest.raises(RuntimeError), transaction.atomic():
            publish_to_user(alice.pk, {"type": "unread.changed"})
            raise RuntimeError
    assert callbacks == []
    assert sent == []


@pytest.mark.django_db
def test_publish_is_noop_when_realtime_is_off(alice, settings, commit):
    settings.CHANNEL_LAYERS = {}
    with commit() as callbacks:
        publish_to_user(alice.pk, {"type": "unread.changed"})
        revoke_sessions(alice.pk)
    assert callbacks == []


@pytest.mark.django_db
def test_publish_failure_is_logged_not_raised(alice, monkeypatch, commit, caplog):
    async def boom(group, message):
        raise ConnectionError("redis down")

    monkeypatch.setattr(get_channel_layer(), "group_send", boom)
    with caplog.at_level(logging.WARNING, logger="apps.realtime.publish"), commit():
        publish_to_user(alice.pk, {"type": "unread.changed"})
    assert "Realtime publish" in caplog.text


@pytest.mark.django_db
def test_slow_layer_is_cut_off(alice, monkeypatch, settings, commit, caplog):
    settings.REALTIME_PUBLISH_TIMEOUT = 0.05

    async def hang(group, message):
        await asyncio.sleep(5)

    monkeypatch.setattr(get_channel_layer(), "group_send", hang)
    started = time.monotonic()
    with caplog.at_level(logging.WARNING, logger="apps.realtime.publish"), commit():
        publish_to_user(alice.pk, {"type": "unread.changed"})
    assert time.monotonic() - started < 2
    assert "Realtime publish" in caplog.text


@pytest.mark.django_db
def test_dm_survives_publish_failure(alice, bob, conv, monkeypatch, commit):
    async def boom(group, message):
        raise ConnectionError("redis down")

    monkeypatch.setattr(get_channel_layer(), "group_send", boom)
    url = reverse("api_v1:messaging:conversation-messages", args=[conv.pk])
    with commit():
        response = as_user(alice).post(url, {"body": "hi"}, format="json")
    assert response.status_code == 201
    assert Message.objects.count() == 1


# ─── notifications ───────────────────────────────────────


@pytest.mark.django_db
def test_notify_publishes_to_recipient(alice, bob, sent, commit):
    with commit():
        notify(bob, actor=alice, verb="follow", target=alice)
    assert sent == [ev(bob, {"type": "notification.created"})]


@pytest.mark.django_db
def test_suppressed_notification_is_not_published(alice, bob, sent, commit):
    Block.objects.create(blocker=bob, blocked=alice)
    with commit():
        assert notify(bob, actor=alice, verb="follow", target=alice) is None
        assert notify(alice, actor=alice, verb="follow", target=alice) is None
    assert sent == []


@pytest.mark.django_db
def test_marking_notifications_read_publishes_unread_changed(alice, bob, sent, commit):
    first = Notification.objects.create(recipient=bob, actor=alice, verb="follow")
    Notification.objects.create(recipient=bob, actor=alice, verb="follow")
    api = as_user(bob)
    read = reverse("api_v1:notifications:notification-read", args=[first.pk])
    mark_all = reverse("api_v1:notifications:notification-mark-all-read")
    with commit():
        assert api.post(read).status_code == 200
        assert api.post(read).status_code == 200  # already read: nothing changes
        assert api.post(mark_all).status_code == 200
        assert api.post(mark_all).status_code == 200  # nothing left to mark
    assert sent == [ev(bob, {"type": "unread.changed"})] * 2


# ─── messaging ───────────────────────────────────────────


@pytest.mark.django_db
def test_dm_publishes_to_both_participants(alice, bob, conv, sent, commit):
    url = reverse("api_v1:messaging:conversation-messages", args=[conv.pk])
    with commit():
        assert as_user(alice).post(url, {"body": "hi"}, format="json").status_code == 201
    created = {"type": "message.created", "conversation_id": conv.pk}
    assert sorted(sent, key=repr) == sorted(
        [ev(bob, {"type": "notification.created"}), ev(bob, created), ev(alice, created)],
        key=repr,
    )


@pytest.mark.django_db
def test_blocked_dm_publishes_nothing(alice, bob, conv, sent, commit):
    Block.objects.create(blocker=bob, blocked=alice)
    url = reverse("api_v1:messaging:conversation-messages", args=[conv.pk])
    with commit():
        assert as_user(alice).post(url, {"body": "hi"}, format="json").status_code == 403
    assert sent == []


@pytest.mark.django_db
def test_reading_a_conversation_publishes_message_read(alice, bob, conv, sent, commit):
    Message.objects.create(conversation=conv, sender=alice, body="hi")
    url = reverse("api_v1:messaging:conversation-read", args=[conv.pk])
    with commit():
        assert as_user(bob).post(url).status_code == 200
        assert as_user(bob).post(url).status_code == 200  # nothing new to mark
    read = {"type": "message.read", "conversation_id": conv.pk}
    assert sorted(sent, key=repr) == sorted([ev(bob, read), ev(alice, read)], key=repr)


@pytest.mark.django_db
def test_read_receipt_is_not_sent_across_a_block(alice, bob, conv, sent, commit):
    Message.objects.create(conversation=conv, sender=alice, body="hi")
    Block.objects.create(blocker=bob, blocked=alice)
    url = reverse("api_v1:messaging:conversation-read", args=[conv.pk])
    with commit():
        assert as_user(bob).post(url).status_code == 200
    assert sent == [ev(bob, {"type": "message.read", "conversation_id": conv.pk})]


@pytest.mark.django_db
def test_already_read_messages_publish_nothing(alice, bob, conv, sent, commit):
    Message.objects.create(conversation=conv, sender=alice, body="hi", read_at=timezone.now())
    url = reverse("api_v1:messaging:conversation-read", args=[conv.pk])
    with commit():
        assert as_user(bob).post(url).status_code == 200
    assert sent == []


# ─── session revocation ──────────────────────────────────


@pytest.mark.django_db
def test_password_change_revokes_sockets(alice, sent, commit):
    url = reverse("api_v1:users:users-change-password")
    payload = {"current_password": PW, "new_password": "New-Pass-456!"}
    with commit():
        assert as_user(alice).post(url, payload, format="json").status_code == 200
    assert sent == [revoked(alice)]


@pytest.mark.django_db
def test_rejected_password_change_revokes_nothing(alice, sent, commit):
    url = reverse("api_v1:users:users-change-password")
    payload = {"current_password": "wrong", "new_password": "New-Pass-456!"}
    with commit():
        assert as_user(alice).post(url, payload, format="json").status_code == 400
    assert sent == []


@pytest.mark.django_db
def test_password_reset_revokes_sockets(alice, sent, commit):
    payload = {
        "uid": urlsafe_base64_encode(force_bytes(alice.pk)),
        "token": default_token_generator.make_token(alice),
        "new_password": "New-Pass-456!",
    }
    url = reverse("api_v1:auth:auth-password-reset-confirm")
    with commit():
        assert APIClient().post(url, payload, format="json").status_code == 204
    assert sent == [revoked(alice)]


@pytest.mark.django_db
def test_account_deletion_revokes_sockets(alice, sent, commit):
    url = reverse("api_v1:users:users-me")
    with commit():
        assert as_user(alice).delete(url, {"password": PW}, format="json").status_code == 204
    assert revoked(alice) in sent


def logged_in(user):
    client = APIClient()
    response = client.post(
        reverse("api_v1:auth:auth-login"),
        {"username": user.username, "password": PW},
        format="json",
    )
    assert response.status_code == 200
    return client


@pytest.mark.django_db
def test_logout_revokes_sockets(alice, sent, commit):
    client = logged_in(alice)
    with commit():
        assert client.post(reverse("api_v1:auth:auth-logout")).status_code == 204
    assert sent == [revoked(alice)]
    # Durable too: a socket that missed the event fails its next check.
    assert User.objects.get(pk=alice.pk).realtime_generation == alice.realtime_generation + 1


@pytest.mark.django_db
def test_logout_with_a_dead_session_revokes_nothing(alice, sent, commit, settings):
    client = APIClient()
    client.cookies[settings.AUTH_REFRESH_COOKIE["key"]] = "not-a-token"
    with commit():
        assert client.post(reverse("api_v1:auth:auth-logout")).status_code == 204
    assert sent == []
    assert User.objects.get(pk=alice.pk).realtime_generation == alice.realtime_generation

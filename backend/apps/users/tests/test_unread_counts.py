import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.messaging.models import Conversation, Message
from apps.notifications.models import Notification

User = get_user_model()
UNREAD = reverse("api_v1:users:users-unread-counts")


def _user(name):
    return User.objects.create_user(username=name, email=f"{name}@x.com", password="x")


def _conv(u1, u2):
    a, b = sorted((u1, u2), key=lambda u: u.id)
    return Conversation.objects.create(participant_a=a, participant_b=b)


def _message(conv, sender, read=False):
    return Message.objects.create(
        conversation=conv, sender=sender, body="hi", read_at=timezone.now() if read else None
    )


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def me():
    return _user("me")


@pytest.mark.django_db
def test_unread_counts_ignore_own_and_foreign_messages(api, me, django_assert_max_num_queries):
    bob, carol = _user("bob"), _user("carol")
    with_bob = _conv(me, bob)
    _message(with_bob, bob)
    _message(with_bob, bob)
    _message(with_bob, bob, read=True)
    _message(with_bob, me)
    foreign = _conv(bob, carol)
    for _ in range(3):
        _message(foreign, carol)
    Notification.objects.create(recipient=me, actor=bob, verb="follow")
    Notification.objects.create(recipient=me, actor=bob, verb="follow")
    Notification.objects.create(recipient=me, actor=bob, verb="follow", read_at=timezone.now())
    Notification.objects.create(recipient=bob, actor=me, verb="follow")
    api.force_authenticate(me)
    with django_assert_max_num_queries(3):
        resp = api.get(UNREAD)
    assert resp.status_code == 200
    assert resp.json() == {"notifications": 2, "messages": 2}


@pytest.mark.django_db
def test_unread_messages_count_across_all_conversations_without_cap(api, me):
    for i in range(30):
        other = _user(f"o{i}")
        _message(_conv(me, other), other)
    api.force_authenticate(me)
    assert api.get(UNREAD).json()["messages"] == 30


@pytest.mark.django_db
def test_unread_counts_require_auth(api):
    assert api.get(UNREAD).status_code == 401

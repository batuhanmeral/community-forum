from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.messaging.models import Conversation, Message

User = get_user_model()
CONVERSATIONS = reverse("api_v1:messaging:conversation-list")


def _user(name):
    return User.objects.create_user(username=name, email=f"{name}@x.com", password="x")


def _conv(u1, u2):
    a, b = sorted((u1, u2), key=lambda u: u.id)
    return Conversation.objects.create(participant_a=a, participant_b=b)


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def me():
    return _user("me")


@pytest.mark.django_db
def test_ten_conversations_within_four_queries(api, me, django_assert_max_num_queries):
    for i in range(10):
        other = _user(f"other{i}")
        conv = _conv(me, other)
        Message.objects.create(conversation=conv, sender=other, body="hi")
        Message.objects.create(conversation=conv, sender=me, body="yo")
    api.force_authenticate(me)
    with django_assert_max_num_queries(4):
        resp = api.get(CONVERSATIONS)
    assert len(resp.data["results"]) == 10


@pytest.mark.django_db
def test_unread_and_last_message_values(api, me):
    bob, carol = _user("bob"), _user("carol")
    conv = _conv(me, bob)
    _conv(me, carol)
    start = timezone.now()
    rows = [
        (bob, "first", None),
        (bob, "second", None),
        (me, "mine", None),
        (bob, "read", start),
        (bob, "latest", start),
    ]
    for i, (sender, body, read_at) in enumerate(rows):
        msg = Message.objects.create(conversation=conv, sender=sender, body=body, read_at=read_at)
        Message.objects.filter(pk=msg.pk).update(created_at=start + timedelta(seconds=i))
    api.force_authenticate(me)
    by_user = {c["other"]["username"]: c for c in api.get(CONVERSATIONS).data["results"]}
    assert by_user["bob"]["unread_count"] == 2
    assert by_user["bob"]["last_message"]["body"] == "latest"
    assert by_user["carol"]["unread_count"] == 0
    assert by_user["carol"]["last_message"] is None


@pytest.mark.django_db
def test_ten_messages_within_three_queries(api, me, django_assert_max_num_queries):
    other = _user("other")
    conv = _conv(me, other)
    for i in range(10):
        Message.objects.create(conversation=conv, sender=other if i % 2 else me, body=f"m{i}")
    api.force_authenticate(me)
    url = reverse("api_v1:messaging:conversation-messages", args=[conv.pk])
    with django_assert_max_num_queries(3):
        resp = api.get(url)
    assert len(resp.data["results"]) == 10

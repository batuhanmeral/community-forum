from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.messaging.models import Conversation, Message

User = get_user_model()
LIST = reverse("api_v1:messaging:conversation-list")


def msgs_url(pk):
    return reverse("api_v1:messaging:conversation-messages", args=[pk])


def _user(name, **extra):
    return User.objects.create_user(username=name, email=f"{name}@x.com", password="x", **extra)


def _conv(u1, u2):
    a, b = sorted((u1, u2), key=lambda u: u.id)
    return Conversation.objects.create(participant_a=a, participant_b=b)


@pytest.fixture
def api():
    return APIClient()


@pytest.mark.django_db
class TestMessagePages:
    def test_first_page_is_the_newest_messages(self, api):
        alice, bob = _user("alice"), _user("bob")
        conv = _conv(alice, bob)
        start = timezone.now()
        for i in range(25):
            m = Message.objects.create(conversation=conv, sender=bob, body=f"m{i}")
            Message.objects.filter(pk=m.pk).update(created_at=start + timedelta(seconds=i))
        api.force_authenticate(alice)
        data = api.get(msgs_url(conv.id)).data
        assert [m["body"] for m in data["results"]][:2] == ["m24", "m23"]
        assert len(data["results"]) == 20
        assert data["next"] is not None


@pytest.mark.django_db
class TestConversationOrder:
    def test_most_recent_activity_first(self, api):
        alice, bob, carol = _user("alice"), _user("bob"), _user("carol")
        old = _conv(alice, bob)
        new = _conv(alice, carol)
        Message.objects.create(conversation=old, sender=bob, body="latest")
        api.force_authenticate(alice)
        ids = [c["id"] for c in api.get(LIST).data["results"]]
        assert ids == [old.id, new.id]


@pytest.mark.django_db
class TestInactiveRecipient:
    def test_cannot_start_conversation_with_deactivated_user(self, api):
        alice = _user("alice")
        _user("ghost", is_active=False)
        api.force_authenticate(alice)
        resp = api.post(LIST, {"username": "ghost"}, format="json")
        assert resp.status_code == 400

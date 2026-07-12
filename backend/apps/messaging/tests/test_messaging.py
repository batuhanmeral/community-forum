import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.messaging.models import Conversation, Message
from apps.notifications.models import Notification

User = get_user_model()
LIST = reverse("api_v1:messaging:conversation-list")


def msgs_url(pk):
    return reverse("api_v1:messaging:conversation-messages", args=[pk])


def read_url(pk):
    return reverse("api_v1:messaging:conversation-read", args=[pk])


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="alice", email="a@x.com", password="x")


@pytest.fixture
def bob(db):
    return User.objects.create_user(username="bob", email="b@x.com", password="x")


@pytest.fixture
def carol(db):
    return User.objects.create_user(username="carol", email="c@x.com", password="x")


@pytest.fixture
def conv(alice, bob):
    a, b = sorted((alice, bob), key=lambda u: u.id)
    return Conversation.objects.create(participant_a=a, participant_b=b)


@pytest.mark.django_db
class TestConversationCreate:
    def test_anonymous_rejected(self, api):
        assert api.get(LIST).status_code == 401

    def test_start_conversation(self, api, alice, bob):
        api.force_authenticate(alice)
        resp = api.post(LIST, {"username": "bob"}, format="json")
        assert resp.status_code == 201
        assert resp.data["other"]["username"] == "bob"
        assert Conversation.objects.count() == 1

    def test_create_is_idempotent(self, api, alice, bob):
        api.force_authenticate(alice)
        api.post(LIST, {"username": "bob"}, format="json")
        api.post(LIST, {"username": "bob"}, format="json")
        assert Conversation.objects.count() == 1

    def test_participants_sorted_by_id(self, api, alice, bob):
        api.force_authenticate(bob)
        api.post(LIST, {"username": "alice"}, format="json")
        c = Conversation.objects.get()
        assert c.participant_a_id < c.participant_b_id

    def test_cannot_self_chat(self, api, alice):
        api.force_authenticate(alice)
        resp = api.post(LIST, {"username": "alice"}, format="json")
        assert resp.status_code == 400

    def test_unknown_user_rejected(self, api, alice):
        api.force_authenticate(alice)
        resp = api.post(LIST, {"username": "ghost"}, format="json")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestInbox:
    def test_lists_only_my_conversations(self, api, alice, bob, carol):
        a, b = sorted((alice, bob), key=lambda u: u.id)
        Conversation.objects.create(participant_a=a, participant_b=b)
        a2, c2 = sorted((bob, carol), key=lambda u: u.id)
        Conversation.objects.create(participant_a=a2, participant_b=c2)
        api.force_authenticate(alice)
        resp = api.get(LIST)
        assert resp.data["count"] == 1

    def test_unread_count_excludes_own_messages(self, api, alice, bob, conv):
        Message.objects.create(conversation=conv, sender=bob, body="hi")
        Message.objects.create(conversation=conv, sender=alice, body="self")
        api.force_authenticate(alice)
        row = api.get(LIST).data["results"][0]
        assert row["unread_count"] == 1

    def test_last_message_shown(self, api, alice, bob, conv):
        Message.objects.create(conversation=conv, sender=bob, body="first")
        Message.objects.create(conversation=conv, sender=alice, body="second")
        api.force_authenticate(alice)
        row = api.get(LIST).data["results"][0]
        assert row["last_message"]["body"] == "second"


@pytest.mark.django_db
class TestMessages:
    def test_non_participant_blocked(self, api, conv, carol):
        api.force_authenticate(carol)
        assert api.get(msgs_url(conv.id)).status_code == 403

    def test_send_message(self, api, conv, alice, bob):
        api.force_authenticate(alice)
        resp = api.post(msgs_url(conv.id), {"body": "hi"}, format="json")
        assert resp.status_code == 201
        assert resp.data["sender"] == alice.id
        # DM notification
        assert Notification.objects.filter(recipient=bob, verb="dm").exists()

    def test_self_message_no_self_notification(self, api, conv, alice):
        api.force_authenticate(alice)
        api.post(msgs_url(conv.id), {"body": "hi"}, format="json")
        assert not Notification.objects.filter(recipient=alice, verb="dm").exists()

    def test_empty_body_rejected(self, api, conv, alice):
        api.force_authenticate(alice)
        assert api.post(msgs_url(conv.id), {"body": "  "}, format="json").status_code == 400

    def test_history_in_order(self, api, conv, alice, bob):
        Message.objects.create(conversation=conv, sender=alice, body="a")
        Message.objects.create(conversation=conv, sender=bob, body="b")
        api.force_authenticate(alice)
        bodies = [m["body"] for m in api.get(msgs_url(conv.id)).data["results"]]
        assert bodies == ["a", "b"]


@pytest.mark.django_db
class TestRead:
    def test_marks_incoming_messages_read(self, api, conv, alice, bob):
        m1 = Message.objects.create(conversation=conv, sender=bob, body="hi")
        m2 = Message.objects.create(conversation=conv, sender=alice, body="self")
        api.force_authenticate(alice)
        resp = api.post(read_url(conv.id))
        assert resp.status_code == 200
        assert resp.data["marked_read"] == 1
        m1.refresh_from_db()
        m2.refresh_from_db()
        assert m1.read_at is not None
        assert m2.read_at is None  # own message untouched

    def test_non_participant_blocked(self, api, conv, carol):
        api.force_authenticate(carol)
        assert api.post(read_url(conv.id)).status_code == 403

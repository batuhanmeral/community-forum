import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.notifications.models import Notification
from apps.social.models import Block, Follow

User = get_user_model()

BLOCKED_LIST = reverse("api_v1:social:user-blocked-list")


def block_url(username):
    return reverse("api_v1:social:user-block", args=[username])


def follow_url(username):
    return reverse("api_v1:social:user-follow", args=[username])


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="alice", email="a@x.com", password="x")


@pytest.fixture
def bob(db):
    return User.objects.create_user(username="bob", email="b@x.com", password="x")


@pytest.mark.django_db
class TestBlockToggle:
    def test_requires_auth(self, api, bob):
        assert api.post(block_url("bob")).status_code == 401

    def test_block_and_unblock(self, api, alice, bob):
        api.force_authenticate(alice)
        resp = api.post(block_url("bob"))
        assert resp.status_code == 201
        assert Block.objects.filter(blocker=alice, blocked=bob).exists()
        resp = api.delete(block_url("bob"))
        assert resp.status_code == 200
        assert not Block.objects.filter(blocker=alice, blocked=bob).exists()

    def test_block_is_idempotent(self, api, alice, bob):
        api.force_authenticate(alice)
        api.post(block_url("bob"))
        assert api.post(block_url("bob")).status_code == 200
        assert Block.objects.count() == 1

    def test_cannot_block_self(self, api, alice):
        api.force_authenticate(alice)
        assert api.post(block_url("alice")).status_code == 400

    def test_block_severs_follows_both_ways(self, api, alice, bob):
        Follow.objects.create(follower=alice, followed=bob)
        Follow.objects.create(follower=bob, followed=alice)
        api.force_authenticate(alice)
        api.post(block_url("bob"))
        assert Follow.objects.count() == 0

    def test_blocked_pair_cannot_follow(self, api, alice, bob):
        api.force_authenticate(alice)
        api.post(block_url("bob"))
        assert api.post(follow_url("bob")).status_code == 400
        # the blocked side cannot follow back either
        api.force_authenticate(bob)
        assert api.post(follow_url("alice")).status_code == 400

    def test_blocked_list(self, api, alice, bob):
        api.force_authenticate(alice)
        api.post(block_url("bob"))
        resp = api.get(BLOCKED_LIST)
        assert resp.status_code == 200
        assert [u["username"] for u in resp.data["results"]] == ["bob"]

    def test_profile_exposes_is_blocked(self, api, alice, bob):
        api.force_authenticate(alice)
        api.post(block_url("bob"))
        resp = api.get(reverse("api_v1:users:users-profile", args=["bob"]))
        assert resp.data["is_blocked"] is True


@pytest.mark.django_db
class TestBlockEnforcement:
    def _start_conversation(self, api, username):
        return api.post(
            reverse("api_v1:messaging:conversation-list"),
            {"username": username},
            format="json",
        )

    def test_cannot_start_conversation_with_blocked(self, api, alice, bob):
        Block.objects.create(blocker=alice, blocked=bob)
        api.force_authenticate(alice)
        assert self._start_conversation(api, "bob").status_code == 400

    def test_blocked_user_cannot_start_conversation(self, api, alice, bob):
        Block.objects.create(blocker=alice, blocked=bob)
        api.force_authenticate(bob)
        assert self._start_conversation(api, "alice").status_code == 400

    def test_block_stops_messages_in_existing_conversation(self, api, alice, bob):
        api.force_authenticate(alice)
        conv_id = self._start_conversation(api, "bob").data["id"]
        Block.objects.create(blocker=alice, blocked=bob)
        api.force_authenticate(bob)
        resp = api.post(
            reverse("api_v1:messaging:conversation-messages", args=[conv_id]),
            {"body": "hi"},
            format="json",
        )
        assert resp.status_code == 403

    def test_notify_suppressed_when_recipient_blocked_actor(self, alice, bob):
        from apps.notifications.services import notify

        Block.objects.create(blocker=alice, blocked=bob)
        assert notify(alice, actor=bob, verb="follow", target=bob) is None
        assert Notification.objects.count() == 0
        # reverse direction still notifies (bob blocked nobody)
        assert notify(bob, actor=alice, verb="follow", target=alice) is not None

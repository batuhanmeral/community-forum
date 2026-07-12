import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.notifications.models import Notification
from apps.social.models import Follow

User = get_user_model()


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


def follow_url(username):
    return reverse("api_v1:social:user-follow", args=[username])


def followers_url(username):
    return reverse("api_v1:social:user-followers", args=[username])


def following_url(username):
    return reverse("api_v1:social:user-following", args=[username])


def profile_url(username):
    return reverse("api_v1:users:users-profile", args=[username])


@pytest.mark.django_db
class TestFollowToggle:
    def test_anonymous_rejected(self, api, bob):
        assert api.post(follow_url("bob")).status_code == 401

    def test_follow_creates_and_notifies(self, api, alice, bob):
        api.force_authenticate(alice)
        resp = api.post(follow_url("bob"))
        assert resp.status_code == 201
        assert resp.data["is_following"] is True
        assert Follow.objects.filter(follower=alice, followed=bob).exists()
        assert Notification.objects.filter(recipient=bob, verb="follow").exists()

    def test_follow_idempotent(self, api, alice, bob):
        api.force_authenticate(alice)
        api.post(follow_url("bob"))
        resp = api.post(follow_url("bob"))
        assert resp.status_code == 200
        assert Follow.objects.count() == 1
        assert Notification.objects.filter(recipient=bob, verb="follow").count() == 1

    def test_unfollow(self, api, alice, bob):
        Follow.objects.create(follower=alice, followed=bob)
        api.force_authenticate(alice)
        resp = api.delete(follow_url("bob"))
        assert resp.status_code == 200
        assert resp.data["is_following"] is False
        assert not Follow.objects.exists()

    def test_unknown_user_404(self, api, alice):
        api.force_authenticate(alice)
        assert api.post(follow_url("ghost")).status_code == 404

    def test_cannot_self_follow(self, api, alice):
        api.force_authenticate(alice)
        resp = api.post(follow_url("alice"))
        assert resp.status_code == 400


@pytest.mark.django_db
class TestFollowLists:
    def test_followers_list(self, api, alice, bob, carol):
        Follow.objects.create(follower=bob, followed=alice)
        Follow.objects.create(follower=carol, followed=alice)
        resp = api.get(followers_url("alice"))
        assert resp.status_code == 200
        names = {u["username"] for u in resp.data["results"]}
        assert names == {"bob", "carol"}

    def test_following_list(self, api, alice, bob, carol):
        Follow.objects.create(follower=alice, followed=bob)
        Follow.objects.create(follower=alice, followed=carol)
        resp = api.get(following_url("alice"))
        names = {u["username"] for u in resp.data["results"]}
        assert names == {"bob", "carol"}

    def test_is_following_flag_for_viewer(self, api, alice, bob, carol):
        Follow.objects.create(follower=alice, followed=carol)
        api.force_authenticate(alice)
        rows = api.get(following_url("alice")).data["results"]
        assert rows[0]["is_following"] is True


@pytest.mark.django_db
class TestProfile:
    def test_profile_hides_email(self, api, alice):
        resp = api.get(profile_url("alice"))
        assert resp.status_code == 200
        assert "email" not in resp.data
        assert resp.data["username"] == "alice"

    def test_profile_counts(self, api, alice, bob, carol):
        Follow.objects.create(follower=bob, followed=alice)
        Follow.objects.create(follower=carol, followed=alice)
        Follow.objects.create(follower=alice, followed=bob)
        resp = api.get(profile_url("alice"))
        assert resp.data["followers_count"] == 2
        assert resp.data["following_count"] == 1

    def test_profile_is_following_for_viewer(self, api, alice, bob):
        Follow.objects.create(follower=alice, followed=bob)
        api.force_authenticate(alice)
        resp = api.get(profile_url("bob"))
        assert resp.data["is_following"] is True

    def test_profile_is_following_false_for_self(self, api, alice):
        api.force_authenticate(alice)
        resp = api.get(profile_url("alice"))
        assert resp.data["is_following"] is False

    def test_me_still_includes_email(self, api, alice):
        api.force_authenticate(alice)
        resp = api.get(reverse("api_v1:users:users-me"))
        assert resp.data["email"] == "a@x.com"
        assert "followers_count" in resp.data

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.communities.models import Community, Membership

User = get_user_model()


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="alice", email="a@x.com", password="StrongPass123!")


@pytest.fixture
def bob(db):
    return User.objects.create_user(username="bob", email="b@x.com", password="StrongPass123!")


@pytest.fixture
def authed(api, alice):
    api.force_authenticate(alice)
    return api


@pytest.fixture
def community(alice):
    return Community.objects.create(slug="python", name="Python", creator=alice)


LIST = reverse("api_v1:communities:community-list")


def detail(slug):
    return reverse("api_v1:communities:community-detail", args=[slug])


def membership_url(slug):
    return reverse("api_v1:communities:community-membership", args=[slug])


@pytest.mark.django_db
class TestCommunityCRUD:
    def test_anonymous_can_list(self, api, community):
        resp = api.get(LIST)
        assert resp.status_code == 200
        assert resp.data["count"] == 1

    def test_anonymous_cannot_create(self, api):
        resp = api.post(LIST, {"slug": "go", "name": "Go"}, format="json")
        assert resp.status_code == 401

    def test_authed_can_create_and_becomes_admin(self, authed, alice):
        resp = authed.post(LIST, {"slug": "go", "name": "Go"}, format="json")
        assert resp.status_code == 201
        c = Community.objects.get(slug="go")
        assert c.creator == alice
        assert Membership.objects.filter(
            user=alice, community=c, role=Membership.Role.ADMIN
        ).exists()

    def test_detail_lookup_by_slug(self, api, community):
        resp = api.get(detail("python"))
        assert resp.status_code == 200
        assert resp.data["slug"] == "python"

    def test_only_creator_can_update(self, api, community, bob):
        api.force_authenticate(bob)
        resp = api.patch(detail("python"), {"description": "x"}, format="json")
        assert resp.status_code == 403

    def test_creator_can_toggle_nsfw(self, api, community, alice):
        api.force_authenticate(alice)
        resp = api.patch(detail("python"), {"is_nsfw": True}, format="json")
        assert resp.status_code == 200
        community.refresh_from_db()
        assert community.is_nsfw is True

    def test_search(self, api, community, alice):
        Community.objects.create(slug="rust", name="Rust", creator=alice)
        resp = api.get(LIST, {"search": "py"})
        assert resp.status_code == 200
        slugs = [c["slug"] for c in resp.data["results"]]
        assert slugs == ["python"]


@pytest.mark.django_db
class TestMembership:
    def test_anonymous_cannot_join(self, api, community):
        resp = api.post(membership_url("python"))
        assert resp.status_code == 401

    def test_join_creates_membership(self, api, community, bob):
        api.force_authenticate(bob)
        resp = api.post(membership_url("python"))
        assert resp.status_code == 201
        assert Membership.objects.filter(user=bob, community=community).exists()

    def test_join_is_idempotent(self, api, community, bob):
        api.force_authenticate(bob)
        api.post(membership_url("python"))
        resp = api.post(membership_url("python"))
        assert resp.status_code == 200
        assert Membership.objects.filter(user=bob, community=community).count() == 1

    def test_leave_removes_membership(self, api, community, bob):
        api.force_authenticate(bob)
        api.post(membership_url("python"))
        resp = api.delete(membership_url("python"))
        assert resp.status_code == 204
        assert not Membership.objects.filter(user=bob, community=community).exists()

    def test_creator_cannot_leave(self, api, community, alice):
        api.force_authenticate(alice)
        resp = api.delete(membership_url("python"))
        assert resp.status_code == 400

    def test_patch_notify_level(self, api, community, bob):
        api.force_authenticate(bob)
        api.post(membership_url("python"))
        resp = api.patch(
            membership_url("python"), {"notify_level": "posts_only"}, format="json"
        )
        assert resp.status_code == 200
        assert resp.data["notify_level"] == "posts_only"

    def test_patch_requires_membership(self, api, community, bob):
        api.force_authenticate(bob)
        resp = api.patch(
            membership_url("python"), {"notify_level": "off"}, format="json"
        )
        assert resp.status_code == 400

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.communities.models import Community

User = get_user_model()


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="alice", email="a@x.com", password="x")


@pytest.fixture
def community(alice):
    return Community.objects.create(slug="py", name="Python", creator=alice)


@pytest.fixture
def authed(api, alice):
    api.force_authenticate(alice)
    return api


def detail_url():
    return reverse("api_v1:communities:community-detail", args=["py"])


@pytest.mark.django_db
class TestLengthCaps:
    def test_bio_over_cap_rejected(self, authed):
        resp = authed.patch(reverse("api_v1:users:users-me"), {"bio": "x" * 501}, format="json")
        assert resp.status_code == 400
        assert "bio" in resp.data

    def test_bio_at_cap_accepted(self, authed):
        resp = authed.patch(reverse("api_v1:users:users-me"), {"bio": "x" * 500}, format="json")
        assert resp.status_code == 200

    def test_community_description_over_cap_rejected(self, authed, community):
        resp = authed.patch(detail_url(), {"description": "x" * 501}, format="json")
        assert resp.status_code == 400
        assert "description" in resp.data

    def test_community_description_at_cap_accepted(self, authed, community):
        resp = authed.patch(detail_url(), {"description": "x" * 500}, format="json")
        assert resp.status_code == 200

    def test_banned_keywords_over_cap_rejected(self, authed, community):
        resp = authed.patch(detail_url(), {"banned_keywords": "x" * 2001}, format="json")
        assert resp.status_code == 400
        assert "banned_keywords" in resp.data

    def test_banned_keywords_at_cap_accepted(self, authed, community):
        resp = authed.patch(detail_url(), {"banned_keywords": "x" * 2000}, format="json")
        assert resp.status_code == 200

    def test_rule_description_over_cap_rejected(self, authed, community):
        url = reverse("api_v1:communities:community-rules", args=["py"])
        resp = authed.post(url, {"short": "r", "description": "x" * 501}, format="json")
        assert resp.status_code == 400
        assert "description" in resp.data

    def test_rule_description_at_cap_accepted(self, authed, community):
        url = reverse("api_v1:communities:community-rules", args=["py"])
        resp = authed.post(url, {"short": "r", "description": "x" * 500}, format="json")
        assert resp.status_code == 201

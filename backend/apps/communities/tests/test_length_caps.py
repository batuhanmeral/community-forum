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


ME = reverse("api_v1:users:users-me")
DETAIL = reverse("api_v1:communities:community-detail", args=["py"])
RULES = reverse("api_v1:communities:community-rules", args=["py"])


@pytest.mark.django_db
class TestLengthCaps:
    @pytest.mark.parametrize(
        "method, url, field, length, extra",
        [
            pytest.param("patch", ME, "bio", 501, {}, id="bio"),
            pytest.param("patch", DETAIL, "description", 501, {}, id="community-description"),
            pytest.param("patch", DETAIL, "banned_keywords", 2001, {}, id="banned-keywords"),
            pytest.param("post", RULES, "description", 501, {"short": "r"}, id="rule-description"),
        ],
    )
    def test_length_cap_exceeded_rejected(
        self, authed, community, method, url, field, length, extra
    ):
        resp = getattr(authed, method)(url, {**extra, field: "x" * length}, format="json")
        assert resp.status_code == 400
        assert field in resp.data

    @pytest.mark.parametrize(
        "method, url, field, length, extra, status",
        [
            pytest.param("patch", ME, "bio", 500, {}, 200, id="bio"),
            pytest.param("patch", DETAIL, "description", 500, {}, 200, id="community-description"),
            pytest.param("patch", DETAIL, "banned_keywords", 2000, {}, 200, id="banned-keywords"),
            pytest.param(
                "post", RULES, "description", 500, {"short": "r"}, 201, id="rule-description"
            ),
        ],
    )
    def test_length_cap_at_limit_accepted(
        self, authed, community, method, url, field, length, extra, status
    ):
        resp = getattr(authed, method)(url, {**extra, field: "x" * length}, format="json")
        assert resp.status_code == status

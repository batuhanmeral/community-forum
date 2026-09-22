import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

User = get_user_model()
URL = reverse("api_v1:users:users-leaderboard")


@pytest.fixture
def api():
    return APIClient()


@pytest.mark.django_db
class TestLeaderboard:
    def test_ordered_by_total_karma(self, api):
        User.objects.create_user(
            username="low", email="l@x.com", password="x", post_karma=1, comment_karma=1
        )
        User.objects.create_user(
            username="high", email="h@x.com", password="x", post_karma=50, comment_karma=10
        )
        resp = api.get(URL)
        assert resp.status_code == 200
        names = [u["username"] for u in resp.data]
        assert names[:2] == ["high", "low"]

    def test_inactive_users_excluded(self, api):
        User.objects.create_user(
            username="ghost", email="g@x.com", password="x", post_karma=999, is_active=False
        )
        resp = api.get(URL)
        assert "ghost" not in [u["username"] for u in resp.data]

    def test_limited_to_ten(self, api):
        for i in range(12):
            User.objects.create_user(username=f"u{i}", email=f"u{i}@x.com", password="x")
        resp = api.get(URL)
        assert len(resp.data) == 10

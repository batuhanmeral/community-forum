import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

User = get_user_model()


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="alice", email="alice@example.com", password="StrongPass123!"
    )


@pytest.mark.django_db
class TestRegister:
    url = reverse("api_v1:auth:auth-register")

    def test_register_creates_user(self, api):
        resp = api.post(
            self.url,
            {"username": "bob", "email": "bob@example.com", "password": "StrongPass123!"},
            format="json",
        )
        assert resp.status_code == 201
        assert User.objects.filter(username="bob").exists()
        assert "password" not in resp.data

    def test_register_rejects_weak_password(self, api):
        resp = api.post(
            self.url,
            {"username": "bob", "email": "bob@example.com", "password": "123"},
            format="json",
        )
        assert resp.status_code == 400
        assert "password" in resp.data

    def test_register_rejects_duplicate_username(self, api, user):
        resp = api.post(
            self.url,
            {"username": "alice", "email": "other@example.com", "password": "StrongPass123!"},
            format="json",
        )
        assert resp.status_code == 400
        assert "username" in resp.data

    def test_register_rejects_duplicate_email(self, api, user):
        resp = api.post(
            self.url,
            {"username": "other", "email": "alice@example.com", "password": "StrongPass123!"},
            format="json",
        )
        assert resp.status_code == 400
        assert "email" in resp.data


@pytest.mark.django_db
class TestLoginRefresh:
    login_url = reverse("api_v1:auth:auth-login")
    refresh_url = reverse("api_v1:auth:auth-refresh")
    logout_url = reverse("api_v1:auth:auth-logout")

    def _login(self, api):
        return api.post(
            self.login_url,
            {"username": "alice", "password": "StrongPass123!"},
            format="json",
        )

    def test_login_returns_access_and_sets_refresh_cookie(self, api, user):
        resp = self._login(api)
        assert resp.status_code == 200
        assert "access" in resp.data
        assert "refresh" not in resp.data
        cookie = resp.cookies["nexus_refresh"]
        assert cookie.value
        assert cookie["httponly"] and cookie["samesite"] == "Strict"
        assert cookie["path"] == "/api/v1/auth/"

    def test_login_rejects_bad_password(self, api, user):
        resp = api.post(
            self.login_url,
            {"username": "alice", "password": "wrong"},
            format="json",
        )
        assert resp.status_code == 401
        assert "nexus_refresh" not in resp.cookies

    def test_refresh_reads_the_cookie_and_rotates_it(self, api, user):
        first = self._login(api).cookies["nexus_refresh"].value
        resp = api.post(self.refresh_url)
        assert resp.status_code == 200
        assert "access" in resp.data and "refresh" not in resp.data
        rotated = resp.cookies["nexus_refresh"].value
        assert rotated and rotated != first

    def test_refresh_ignores_a_token_in_the_body(self, api, user):
        token = self._login(api).cookies["nexus_refresh"].value
        anonymous = APIClient()
        assert (
            anonymous.post(self.refresh_url, {"refresh": token}, format="json").status_code == 401
        )

    def test_logout_blacklists_the_cookie_and_clears_it(self, api, user):
        token = self._login(api).cookies["nexus_refresh"].value
        resp = api.post(self.logout_url)
        assert resp.status_code == 204
        assert resp.cookies["nexus_refresh"].value == ""
        reuse = APIClient()
        reuse.cookies["nexus_refresh"] = token
        assert reuse.post(self.refresh_url).status_code == 401

    def test_logout_without_a_session_leaves_cookies_alone(self, api):
        resp = APIClient().post(self.logout_url)
        assert resp.status_code == 204
        assert "nexus_refresh" not in resp.cookies

    def test_logout_is_not_throttled(self, api, user, monkeypatch):
        from rest_framework.throttling import ScopedRateThrottle

        monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"refresh": "1/min"})
        statuses = [APIClient().post(self.logout_url).status_code for _ in range(3)]
        assert statuses == [204, 204, 204]

    def test_login_rejects_form_posts(self, api, user):
        resp = APIClient().post(self.login_url, {"username": "alice", "password": "StrongPass123!"})
        assert resp.status_code == 415
        assert "nexus_refresh" not in resp.cookies


@pytest.mark.django_db
class TestMe:
    me_url = reverse("api_v1:users:users-me")
    login_url = reverse("api_v1:auth:auth-login")

    def test_me_requires_auth(self, api):
        resp = api.get(self.me_url)
        assert resp.status_code == 401

    def test_me_returns_current_user(self, api, user):
        login = api.post(
            self.login_url,
            {"username": "alice", "password": "StrongPass123!"},
            format="json",
        )
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        resp = api.get(self.me_url)
        assert resp.status_code == 200
        assert resp.data["username"] == "alice"
        assert resp.data["email"] == "alice@example.com"
        assert resp.data["total_karma"] == 0

    def test_me_can_update_bio(self, api, user):
        login = api.post(
            self.login_url,
            {"username": "alice", "password": "StrongPass123!"},
            format="json",
        )
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        resp = api.patch(self.me_url, {"bio": "hello"}, format="json")
        assert resp.status_code == 200
        user.refresh_from_db()
        assert user.bio == "hello"

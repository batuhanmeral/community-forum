import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()
LOGIN = reverse("api_v1:auth:auth-login")
REFRESH = reverse("api_v1:auth:auth-refresh")
RESET_CONFIRM = reverse("api_v1:auth:auth-password-reset-confirm")
ME = reverse("api_v1:users:users-me")
PASSWORD = reverse("api_v1:users:users-change-password")
OLD_PW = "OldPass123!x"
NEW_PW = "NewPass456!y"


def _bearer(access: str) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


def _login(password=OLD_PW) -> dict:
    return APIClient().post(LOGIN, {"username": "alice", "password": password}, format="json").data


def _refresh(token: str) -> int:
    return APIClient().post(REFRESH, {"refresh": token}, format="json").status_code


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="alice", email="a@x.com", password=OLD_PW)


@pytest.mark.django_db
class TestRevocation:
    def test_password_change_revokes_old_tokens_and_returns_new_pair(self, alice):
        old = _login()
        client = _bearer(old["access"])
        resp = client.post(
            PASSWORD, {"current_password": OLD_PW, "new_password": NEW_PW}, format="json"
        )
        assert resp.status_code == 200
        assert client.get(ME).status_code == 401
        assert _refresh(old["refresh"]) == 401
        assert _bearer(resp.data["access"]).get(ME).status_code == 200
        assert _refresh(resp.data["refresh"]) == 200

    def test_password_reset_revokes_sessions(self, alice):
        old = _login()
        payload = {
            "uid": urlsafe_base64_encode(force_bytes(alice.pk)),
            "token": default_token_generator.make_token(alice),
            "new_password": NEW_PW,
        }
        assert APIClient().post(RESET_CONFIRM, payload, format="json").status_code == 204
        assert _refresh(old["refresh"]) == 401
        assert _bearer(old["access"]).get(ME).status_code == 401

    def test_token_without_password_claim_is_rejected(self, alice):
        # Tokens minted before revocation checks were enabled carry no claim.
        legacy = RefreshToken()
        legacy["user_id"] = str(alice.pk)
        assert _refresh(str(legacy)) == 401


@pytest.mark.django_db
class TestAuthThrottle:
    def test_login_uses_auth_scope(self, alice, monkeypatch):
        from rest_framework.throttling import ScopedRateThrottle

        monkeypatch.setattr(
            ScopedRateThrottle,
            "THROTTLE_RATES",
            {"auth": "2/min", "write": "100/min", "vote": "100/min"},
        )
        statuses = [
            APIClient()
            .post(LOGIN, {"username": "alice", "password": "wrong"}, format="json")
            .status_code
            for _ in range(3)
        ]
        assert statuses == [401, 401, 429]

    def test_refresh_has_its_own_throttle_scope(self, alice, monkeypatch):
        from rest_framework.throttling import ScopedRateThrottle

        monkeypatch.setattr(
            ScopedRateThrottle,
            "THROTTLE_RATES",
            {"auth": "2/min", "refresh": "2/min", "write": "100/min", "vote": "100/min"},
        )
        for _ in range(3):
            APIClient().post(LOGIN, {"username": "alice", "password": "wrong"}, format="json")
        assert _refresh("not-a-token") == 401

        assert [_refresh("not-a-token") for _ in range(2)] == [401, 429]

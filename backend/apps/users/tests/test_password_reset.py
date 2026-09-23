import re

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from rest_framework.test import APIClient

User = get_user_model()

RESET = reverse("api_v1:auth:auth-password-reset")
CONFIRM = reverse("api_v1:auth:auth-password-reset-confirm")


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="alice", email="a@x.com", password="OldPass123!")


def _link_params(body: str) -> dict:
    match = re.search(r"reset-password\?uid=(?P<uid>[^&]+)&token=(?P<token>\S+)", body)
    assert match, f"no reset link in email body: {body}"
    return match.groupdict()


@pytest.mark.django_db
class TestPasswordReset:
    def test_request_sends_email(self, api, alice):
        resp = api.post(RESET, {"email": "a@x.com"}, format="json")
        assert resp.status_code == 204
        assert len(mail.outbox) == 1
        assert "a@x.com" in mail.outbox[0].to

    def test_unknown_email_still_204_without_email(self, api, db):
        resp = api.post(RESET, {"email": "ghost@x.com"}, format="json")
        assert resp.status_code == 204
        assert len(mail.outbox) == 0

    def test_full_reset_flow(self, api, alice):
        api.post(RESET, {"email": "a@x.com"}, format="json")
        params = _link_params(mail.outbox[0].body)
        resp = api.post(CONFIRM, {**params, "new_password": "NewPass456!"}, format="json")
        assert resp.status_code == 204
        alice.refresh_from_db()
        assert alice.check_password("NewPass456!")

    def test_bad_token_rejected(self, api, alice):
        api.post(RESET, {"email": "a@x.com"}, format="json")
        params = _link_params(mail.outbox[0].body)
        resp = api.post(
            CONFIRM,
            {"uid": params["uid"], "token": "bad", "new_password": "NewPass456!"},
            format="json",
        )
        assert resp.status_code == 400

    def test_token_single_use(self, api, alice):
        api.post(RESET, {"email": "a@x.com"}, format="json")
        params = _link_params(mail.outbox[0].body)
        api.post(CONFIRM, {**params, "new_password": "NewPass456!"}, format="json")
        resp = api.post(CONFIRM, {**params, "new_password": "OtherPass789!"}, format="json")
        assert resp.status_code == 400

    def test_weak_password_rejected(self, api, alice):
        api.post(RESET, {"email": "a@x.com"}, format="json")
        params = _link_params(mail.outbox[0].body)
        resp = api.post(CONFIRM, {**params, "new_password": "123"}, format="json")
        assert resp.status_code == 400
        alice.refresh_from_db()
        assert alice.check_password("OldPass123!")

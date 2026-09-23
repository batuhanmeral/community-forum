import re

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from rest_framework.test import APIClient

User = get_user_model()

REGISTER = reverse("api_v1:auth:auth-register")
VERIFY = reverse("api_v1:auth:auth-verify-email")
RESEND = reverse("api_v1:auth:auth-verify-email-resend")


@pytest.fixture
def api():
    return APIClient()


def _link_params(body: str) -> dict:
    match = re.search(r"verify-email\?uid=(?P<uid>[^&]+)&token=(?P<token>\S+)", body)
    assert match, f"no verification link in email body: {body}"
    return match.groupdict()


@pytest.mark.django_db
class TestEmailVerification:
    def _register(self, api):
        resp = api.post(
            REGISTER,
            {"username": "bob", "email": "b@x.com", "password": "StrongPass123!"},
            format="json",
        )
        assert resp.status_code == 201
        return User.objects.get(username="bob")

    def test_register_sends_verification_email(self, api):
        self._register(api)
        assert len(mail.outbox) == 1
        assert "verify-email" in mail.outbox[0].body

    def test_verify_flow_sets_flag(self, api):
        user = self._register(api)
        assert user.email_verified is False
        params = _link_params(mail.outbox[0].body)
        resp = api.post(VERIFY, params, format="json")
        assert resp.status_code == 200
        user.refresh_from_db()
        assert user.email_verified is True

    def test_token_invalid_after_verification(self, api):
        self._register(api)
        params = _link_params(mail.outbox[0].body)
        api.post(VERIFY, params, format="json")
        resp = api.post(VERIFY, params, format="json")
        assert resp.status_code == 400

    def test_bad_uid_rejected(self, api, db):
        resp = api.post(VERIFY, {"uid": "xxx", "token": "yyy"}, format="json")
        assert resp.status_code == 400

    def test_resend_requires_auth(self, api, db):
        assert api.post(RESEND).status_code == 401

    def test_resend_sends_new_email(self, api):
        user = self._register(api)
        mail.outbox.clear()
        api.force_authenticate(user)
        resp = api.post(RESEND)
        assert resp.status_code == 204
        assert len(mail.outbox) == 1

    def test_resend_noop_when_verified(self, api):
        user = self._register(api)
        user.email_verified = True
        user.save(update_fields=["email_verified"])
        mail.outbox.clear()
        api.force_authenticate(user)
        resp = api.post(RESEND)
        assert resp.status_code == 204
        assert len(mail.outbox) == 0

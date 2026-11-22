import logging
from smtplib import SMTPException, SMTPRecipientsRefused

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

User = get_user_model()
REGISTER = reverse("api_v1:auth:auth-register")
RESET = reverse("api_v1:auth:auth-password-reset")


@pytest.fixture
def smtp_down(monkeypatch):
    def _fail(*args, **kwargs):
        raise SMTPException("connection refused")

    monkeypatch.setattr("apps.users.emails.send_mail", _fail)


@pytest.mark.django_db(transaction=True)
class TestEmailFailures:
    @pytest.mark.parametrize(
        "error",
        [
            pytest.param(SMTPException("connection refused"), id="connection-refused"),
            pytest.param(
                SMTPRecipientsRefused({"n@x.com": (550, b"no such user")}), id="recipients-refused"
            ),
        ],
    )
    def test_register_succeeds_and_hides_address_when_smtp_fails(self, monkeypatch, caplog, error):
        def _fail(*args, **kwargs):
            raise error

        monkeypatch.setattr("apps.users.emails.send_mail", _fail)
        caplog.set_level(logging.ERROR, logger="apps.users.emails")
        resp = APIClient().post(
            REGISTER,
            {"username": "newbie", "email": "n@x.com", "password": "StrongPass123!"},
            format="json",
        )
        assert resp.status_code == 201
        assert "Email delivery failed" in caplog.text
        assert "n@x.com" not in caplog.text

    def test_password_reset_request_succeeds_when_smtp_is_down(self, smtp_down):
        User.objects.create_user(username="alice", email="a@x.com", password="x")
        resp = APIClient().post(RESET, {"email": "a@x.com"}, format="json")
        assert resp.status_code == 204

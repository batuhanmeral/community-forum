from smtplib import SMTPRecipientsRefused

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.db import transaction
from django.test import override_settings
from django.urls import reverse
from django_tasks_db.models import DBTaskResult
from rest_framework.test import APIClient

from config.settings.base import TASKS

User = get_user_model()


@pytest.fixture(autouse=True)
def database_queue():
    with override_settings(TASKS=TASKS):
        yield


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("flow", ["reset", "register", "resend", "change_email"])
def test_email_waits_for_commit_and_worker(task_command, flow, django_capture_on_commit_callbacks):
    api = APIClient()
    user = User.objects.create_user(username="alice", email="old@example.com", password="x")
    with transaction.atomic(), django_capture_on_commit_callbacks(execute=False) as callbacks:
        if flow == "register":
            response = api.post(
                reverse("api_v1:auth:auth-register"),
                {
                    "username": "bob",
                    "email": "bob@example.com",
                    "password": "StrongPass123!",
                },
            )
            expected_email = "bob@example.com"
            expected_status = 201
        elif flow == "reset":
            response = api.post(reverse("api_v1:auth:auth-password-reset"), {"email": user.email})
            expected_email = user.email
            expected_status = 204
        else:
            api.force_authenticate(user)
            if flow == "resend":
                response = api.post(reverse("api_v1:auth:auth-verify-email-resend"))
                expected_email = user.email
                expected_status = 204
            else:
                response = api.patch(
                    reverse("api_v1:users:users-me"),
                    {"email": "new@example.com", "current_password": "x"},
                )
                expected_email = "new@example.com"
                expected_status = 200
        assert response.status_code == expected_status
        assert len(mail.outbox) == 0
        assert DBTaskResult.objects.count() == 0
    assert len(callbacks) == 1
    queued = DBTaskResult.objects.get().task_result
    # Only a numeric ID and non-reversible state digest; never a token/link/body/address.
    assert isinstance(queued.args[0], int)
    assert len(queued.args) == 2
    assert len(queued.args[1]) == 64
    assert queued.kwargs == {}
    task_command("db_worker", batch=True, verbosity=0)
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [expected_email]
    assert ("reset-password?" if flow == "reset" else "verify-email?") in mail.outbox[0].body


@pytest.mark.django_db(transaction=True)
def test_rollback_does_not_enqueue_email(django_capture_on_commit_callbacks):
    from apps.users.emails import send_verification_email

    user = User.objects.create_user(username="alice", email="a@example.com", password="x")
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        with transaction.atomic():
            send_verification_email(user)
            transaction.set_rollback(True)
    assert callbacks == []
    assert not DBTaskResult.objects.exists()
    assert len(mail.outbox) == 0


@pytest.mark.django_db(transaction=True)
def test_smtp_failure_is_logged_by_worker_only(
    task_command, monkeypatch, caplog, django_capture_on_commit_callbacks
):
    user = User.objects.create_user(username="alice", email="a@example.com", password="x")

    def refuse(*args, **kwargs):
        raise SMTPRecipientsRefused({"a@example.com": (550, b"private SMTP detail")})

    monkeypatch.setattr("apps.users.emails.send_mail", refuse)
    with django_capture_on_commit_callbacks(execute=True):
        response = APIClient().post(
            reverse("api_v1:auth:auth-password-reset"), {"email": user.email}
        )
    assert response.status_code == 204
    assert "Email delivery failed" not in caplog.text
    task_command("db_worker", batch=True, verbosity=0)
    assert "Email delivery failed" in caplog.text
    assert "a@example.com" not in caplog.text
    assert "private SMTP detail" not in caplog.text


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "change", ["deleted", "inactive", "email", "password", "last_login", "verified"]
)
def test_stale_email_task_does_not_send(task_command, change, django_capture_on_commit_callbacks):
    from django.utils import timezone

    from apps.users.emails import send_password_reset_email, send_verification_email

    user = User.objects.create_user(username="alice", email="a@example.com", password="x")
    with django_capture_on_commit_callbacks(execute=True):
        if change == "verified":
            send_verification_email(user)
        else:
            send_password_reset_email(user)
    if change == "deleted":
        user.delete()
    else:
        field, value = {
            "inactive": ("is_active", False),
            "email": ("email", "changed@example.com"),
            "password": ("password", "changed"),
            "last_login": ("last_login", timezone.now()),
            "verified": ("email_verified", True),
        }[change]
        setattr(user, field, value)
        user.save(update_fields=[field])
    task_command("db_worker", batch=True, verbosity=0)
    assert len(mail.outbox) == 0


@pytest.mark.django_db(transaction=True)
def test_reset_existing_and_unknown_accounts_enqueue_equally(
    task_command,
):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    user = User.objects.create_user(username="alice", email="a@example.com", password="x")
    responses, query_shapes = [], []
    for email in [user.email, "unknown@example.com"]:
        before = DBTaskResult.objects.count()
        with CaptureQueriesContext(connection) as queries:
            response = APIClient().post(
                reverse("api_v1:auth:auth-password-reset"), {"email": email}
            )
        assert DBTaskResult.objects.count() == before + 1
        responses.append((response.status_code, response.content))
        query_shapes.append([query["sql"].split()[0] for query in queries])
    assert responses == [(204, b""), (204, b"")]
    assert query_shapes[0] == query_shapes[1]
    task_command("db_worker", batch=True, startup_delay=False, verbosity=0)
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [user.email]


@pytest.mark.django_db(transaction=True)
def test_reset_enqueue_failure_has_identical_response(monkeypatch, caplog):
    from django.db import OperationalError
    from django_tasks_db.backend import DatabaseBackend

    user = User.objects.create_user(username="alice", email="a@example.com", password="x")
    attempts = []

    def fail_enqueue(self, task, args, kwargs):
        attempts.append((task, args, kwargs))
        raise OperationalError("private queue detail a@example.com")

    monkeypatch.setattr(DatabaseBackend, "enqueue", fail_enqueue)
    responses = []
    for email in [user.email, "unknown@example.com"]:
        before = len(attempts)
        response = APIClient().post(reverse("api_v1:auth:auth-password-reset"), {"email": email})
        assert len(attempts) == before + 1
        responses.append((response.status_code, response.content))
    assert responses == [(204, b""), (204, b"")]
    assert caplog.text.count("Password reset queue unavailable") == 2
    assert "private queue detail" not in caplog.text
    assert "a@example.com" not in caplog.text


@pytest.mark.django_db(transaction=True)
def test_unknown_reset_task_performs_lookup_digest_and_token_work(task_command, monkeypatch):
    from django.contrib.auth.tokens import default_token_generator

    from apps.users import emails

    user = User.objects.create_user(username="alice", email="a@example.com", password="x")
    emails.send_password_reset_email(user)
    emails.send_password_reset_email(None)
    digested, tokenized = [], []
    original_state = emails._email_state
    original_token = default_token_generator.make_token

    def digest(recipient, purpose):
        digested.append(recipient.pk)
        return original_state(recipient, purpose)

    def token(recipient):
        tokenized.append(recipient.pk)
        return original_token(recipient)

    monkeypatch.setattr(emails, "_email_state", digest)
    monkeypatch.setattr(default_token_generator, "make_token", token)
    task_command("db_worker")
    assert sorted(digested) == [0, user.pk]
    assert sorted(tokenized) == [0, user.pk]
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [user.email]

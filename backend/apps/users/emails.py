import json
import logging
from smtplib import SMTPException

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.tasks import task
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .tokens import email_verification_token

logger = logging.getLogger(__name__)


def _uid(user) -> str:
    return urlsafe_base64_encode(force_bytes(user.pk))


def _deliver(subject: str, message: str, recipient: str) -> None:
    try:
        send_mail(subject=subject, message=message, from_email=None, recipient_list=[recipient])
    except (SMTPException, OSError) as exc:
        # The user can retry (resend / request again); never fail the request over email.
        # No traceback: SMTP exception args can carry recipient addresses.
        logger.error("Email delivery failed (subject=%r, error=%s)", subject, type(exc).__name__)


def _send_password_reset_email(user, *, deliver: bool = True) -> None:
    token = default_token_generator.make_token(user)
    link = f"{settings.FRONTEND_URL}/reset-password?uid={_uid(user)}&token={token}"
    subject = "Reset your Nexus password"
    message = (
        f"Hi {user.username},\n\n"
        f"Someone requested a password reset for your Nexus account.\n"
        f"If that was you, set a new password here:\n\n{link}\n\n"
        f"If you didn't request this, you can safely ignore this email."
    )
    if deliver:
        _deliver(subject, message, user.email)


def _send_verification_email(user) -> None:
    token = email_verification_token.make_token(user)
    link = f"{settings.FRONTEND_URL}/verify-email?uid={_uid(user)}&token={token}"
    _deliver(
        "Verify your Nexus email",
        f"Hi {user.username},\n\n"
        f"Welcome to Nexus! Confirm your email address here:\n\n{link}\n\n"
        f"If you didn't create this account, you can ignore this email.",
        user.email,
    )


def _email_state(user, purpose: str) -> str:
    # A keyed, non-reversible snapshot prevents delayed jobs from minting fresh
    # links after an address/password/login change. No token or credentials in the queue.
    values = [user.email]
    if purpose == "reset":
        values += [user.password, str(user.last_login)]
    else:
        values += [user.email_verified]
    return salted_hmac(f"users.email.{purpose}", json.dumps(values), algorithm="sha256").hexdigest()


def _recipient(user_id: int, state: str, purpose: str):
    user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
    recipient = user if user is not None else get_user_model()(pk=0)
    state_matches = constant_time_compare(_email_state(recipient, purpose), state)
    if user is None or (purpose == "verify" and user.email_verified) or not state_matches:
        return None
    return user


@task()
def deliver_password_reset(user_id: int, state: str) -> None:
    user = _recipient(user_id, state, "reset")
    # Unknown/stale accounts still perform token and message construction. Only
    # real recipients contact SMTP; sending dummy mail would create abuse traffic.
    recipient = user if user is not None else get_user_model()(pk=0)
    _send_password_reset_email(recipient, deliver=user is not None)


@task()
def deliver_verification(user_id: int, state: str) -> None:
    user = _recipient(user_id, state, "verify")
    if user is not None:
        _send_verification_email(user)


def _enqueue_password_reset(user_id: int, state: str) -> None:
    try:
        deliver_password_reset.enqueue(user_id, state)
    except Exception as exc:
        # Queue availability must not reveal whether the account exists. Never
        # log exception text/tracebacks: they may contain task arguments or PII.
        # nosemgrep: python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure -- logs only the exception class name, no secret
        logger.error("Password reset queue unavailable (error=%s)", type(exc).__name__)


def send_password_reset_email(user) -> None:
    # Both paths compute a state digest and insert exactly one task. ID 0 is
    # deliberately non-existent; the worker does dummy crypto work without sending mail.
    recipient = user if user is not None else get_user_model()(pk=0)
    user_id, state = recipient.pk, _email_state(recipient, "reset")
    transaction.on_commit(lambda: _enqueue_password_reset(user_id, state))


def send_verification_email(user) -> None:
    user_id, state = user.pk, _email_state(user, "verify")
    transaction.on_commit(lambda: deliver_verification.enqueue(user_id, state))

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .tokens import email_verification_token


def _uid(user) -> str:
    return urlsafe_base64_encode(force_bytes(user.pk))


def send_password_reset_email(user) -> None:
    token = default_token_generator.make_token(user)
    link = f"{settings.FRONTEND_URL}/reset-password?uid={_uid(user)}&token={token}"
    send_mail(
        subject="Reset your Nexus password",
        message=(
            f"Hi {user.username},\n\n"
            f"Someone requested a password reset for your Nexus account.\n"
            f"If that was you, set a new password here:\n\n{link}\n\n"
            f"If you didn't request this, you can safely ignore this email."
        ),
        from_email=None,
        recipient_list=[user.email],
    )


def send_verification_email(user) -> None:
    token = email_verification_token.make_token(user)
    link = f"{settings.FRONTEND_URL}/verify-email?uid={_uid(user)}&token={token}"
    send_mail(
        subject="Verify your Nexus email",
        message=(
            f"Hi {user.username},\n\n"
            f"Welcome to Nexus! Confirm your email address here:\n\n{link}\n\n"
            f"If you didn't create this account, you can ignore this email."
        ),
        from_email=None,
        recipient_list=[user.email],
    )

from django.contrib.auth.tokens import PasswordResetTokenGenerator
from rest_framework_simplejwt.tokens import RefreshToken

AUTH_GENERATION_CLAIM = "auth_gen"
# Identifies a login session across refresh rotations (the first refresh token's jti).
SESSION_CLAIM = "sid"


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """Token tied to the email + verified flag, so it expires once used."""

    def _make_hash_value(self, user, timestamp) -> str:
        return f"{user.pk}{user.email}{user.email_verified}{timestamp}"


email_verification_token = EmailVerificationTokenGenerator()


class NexusRefreshToken(RefreshToken):
    """Refresh token that records the user's auth generation (access tokens inherit the claim)."""

    @classmethod
    def for_user(cls, user):
        token = super().for_user(user)
        token[AUTH_GENERATION_CLAIM] = user.auth_generation
        token[SESSION_CLAIM] = str(token["jti"])
        return token

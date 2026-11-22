from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed

from .tokens import AUTH_GENERATION_CLAIM


class NexusJWTAuthentication(JWTAuthentication):
    """JWT auth that also rejects tokens minted before the user's latest wholesale revocation."""

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if validated_token.get(AUTH_GENERATION_CLAIM, 0) != user.auth_generation:
            raise AuthenticationFailed(
                "Session expired. Please log in again.", code="session_revoked"
            )
        return user

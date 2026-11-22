from django.conf import settings


def realtime_enabled() -> bool:
    """Realtime needs a channel layer shared by the API and the realtime service."""
    return bool(settings.CHANNEL_LAYERS)


def user_group(user_id: int) -> str:
    """Every open socket of a user joins this group; publishers address it."""
    return f"user.{user_id}"

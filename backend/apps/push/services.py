from .models import PushPreference, PushSubscription


def drop_subscriptions(user) -> None:
    """Forget every push endpoint of the user (session revoked, credentials changed, account gone)."""
    PushSubscription.objects.filter(user=user).delete()


def erase_push_data(user) -> None:
    drop_subscriptions(user)
    PushPreference.objects.filter(user=user).delete()

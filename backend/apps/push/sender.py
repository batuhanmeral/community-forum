import json
import logging

import requests
from django.conf import settings
from django.utils import timezone
from pywebpush import WebPushException, webpush

from .models import PushSubscription
from .validators import validate_endpoint

logger = logging.getLogger(__name__)

SEND_TIMEOUT = 10
MAX_FAILURES = 5
# How long a push service may hold a message for an offline browser.
TTL_SECONDS = 24 * 3600


class NoRedirectSession(requests.Session):
    """A push service answering with a redirect must not steer us to another host."""

    def request(self, method, url, **kwargs):
        kwargs["allow_redirects"] = False
        return super().request(method, url, **kwargs)


def send_to_subscription(subscription: PushSubscription, payload: dict) -> None:
    """Deliver one message and update the subscription's bookkeeping."""
    try:
        # Checked again here: the allowlist may have tightened since the row was stored.
        validate_endpoint(subscription.endpoint)
    except ValueError:
        subscription.delete()
        return
    outcome = "ok"
    try:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
            },
            data=json.dumps(payload, separators=(",", ":")),
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": settings.VAPID_SUBJECT},
            ttl=TTL_SECONDS,
            timeout=SEND_TIMEOUT,
            requests_session=NoRedirectSession(),
        )
    except WebPushException as exc:
        status = getattr(exc.response, "status_code", None)
        outcome = "gone" if status in (404, 410) else "failed"
    except Exception as exc:  # one broken endpoint must not stop the others
        # Type only: exception text can contain the endpoint, which acts as a capability URL.
        logger.warning("Push delivery failed (error=%s)", type(exc).__name__)
        outcome = "failed"

    if outcome == "gone":
        subscription.delete()
    elif outcome == "failed":
        subscription.failures += 1
        if subscription.failures >= MAX_FAILURES:
            subscription.delete()
        else:
            subscription.save(update_fields=["failures"])
    else:
        subscription.failures = 0
        subscription.last_used = timezone.now()
        subscription.save(update_fields=["failures", "last_used"])

from rest_framework.permissions import SAFE_METHODS
from rest_framework.throttling import ScopedRateThrottle


class WriteThrottleMixin:
    """Apply the view's `throttle_scope` to unsafe methods only; reads keep the anon/user rates."""

    def get_throttles(self):
        throttles = super().get_throttles()
        if self.request.method in SAFE_METHODS:
            return [t for t in throttles if not isinstance(t, ScopedRateThrottle)]
        return throttles

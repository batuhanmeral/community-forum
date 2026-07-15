import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    """DRF throttles use the default cache; clear it between tests so counters reset."""
    cache.clear()
    yield
    cache.clear()

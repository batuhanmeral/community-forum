from contextlib import contextmanager

import pytest
from django.core.cache import cache
from django.db.models.signals import post_init


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    """DRF throttles use the default cache; clear it between tests so counters reset."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def rows_loaded():
    """Count model instances built from DB rows while the context manager is active."""

    @contextmanager
    def counter(*models):
        loaded = dict.fromkeys(models, 0)
        receivers = []
        for model in models:

            def receiver(sender, _model=model, **kwargs):
                loaded[_model] += 1

            post_init.connect(receiver, sender=model, weak=False)
            receivers.append((receiver, model))
        try:
            yield loaded
        finally:
            for receiver, model in receivers:
                post_init.disconnect(receiver, sender=model)

    return counter

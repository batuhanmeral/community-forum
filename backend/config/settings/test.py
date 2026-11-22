from .dev import *  # noqa: F401,F403

TASKS = {"default": {"BACKEND": "django.tasks.backends.immediate.ImmediateBackend"}}

# Hermetic regardless of the developer's REDIS_URL: per-process cache, in-memory channel layer.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
# In-process slots; test_slots.py also runs them against REALTIME_TEST_REDIS_URL when set.
REALTIME_SLOT_REDIS_URL = ""
REALTIME_AUTH_TIMEOUT = 0.2

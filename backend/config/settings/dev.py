from .base import *  # noqa: F401,F403
from .base import REDIS_URL

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Realtime runs as a second process (uvicorn); one-time socket tickets issued by runserver must
# be visible to it, so share Redis instead of the per-process LocMem cache.
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }

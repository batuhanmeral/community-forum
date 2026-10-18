from decouple import Csv, config
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import MIDDLEWARE

DEBUG = False

# No default: prod must never boot with the insecure dev key from base.py.
MIN_SECRET_KEY_LENGTH = 50
SECRET_KEY = config("SECRET_KEY")
if len(SECRET_KEY) < MIN_SECRET_KEY_LENGTH:
    raise ImproperlyConfigured(f"SECRET_KEY must be at least {MIN_SECRET_KEY_LENGTH} characters.")

# Log to stdout so the container runtime collects it; level is tunable without a rebuild.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "default"},
    },
    "root": {"handlers": ["console"], "level": config("LOG_LEVEL", default="INFO").upper()},
}

# Serve collected static files straight from gunicorn via WhiteNoise.
MIDDLEWARE = [
    MIDDLEWARE[0],  # SecurityMiddleware stays first
    "whitenoise.middleware.WhiteNoiseMiddleware",
    *MIDDLEWARE[1:],
]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="", cast=Csv())

# Shared Redis cache — also backs DRF throttle counters and cache_page views,
# which are per-process (LocMem) in dev.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": config("REDIS_URL", default="redis://redis:6379/1"),
    }
}

# Error tracking — enabled only when a DSN is provided.
SENTRY_DSN = config("SENTRY_DSN", default="")
if SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=config("SENTRY_ENVIRONMENT", default="production"),
        traces_sample_rate=config("SENTRY_TRACES_SAMPLE_RATE", default=0.1, cast=float),
        send_default_pii=False,
    )

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True

from datetime import timedelta
from pathlib import Path

from decouple import Csv, config
from config.realtime import channel_layers, websocket_origins

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config("SECRET_KEY", default="dev-insecure-change-me")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
]

LOCAL_APPS = [
    "apps.users",
    "apps.communities",
    "apps.posts",
    "apps.comments",
    "apps.votes",
    "apps.messaging",
    "apps.notifications",
    "apps.social",
    "apps.polls",
    "apps.saves",
    "apps.moderation",
    "apps.modmail",
    "apps.search",
    "apps.realtime",
]

# Local management commands override the task package commands.
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS + ["django_tasks_db"]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Container healthchecks probe over plain HTTP; inert while SECURE_SSL_REDIRECT is off.
SECURE_REDIRECT_EXEMPT = [r"^api/v1/health/$"]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME", default="nexus"),
        "USER": config("DB_USER", default="nexus"),
        "PASSWORD": config("DB_PASSWORD", default="nexus"),
        "HOST": config("DB_HOST", default="localhost"),
        "PORT": config("DB_PORT", default="5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticatedOrReadOnly",),
    "DEFAULT_PAGINATION_CLASS": "config.pagination.DefaultPagination",
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": config("THROTTLE_ANON", default="60/min"),
        "user": config("THROTTLE_USER", default="600/min"),
        "auth": config("THROTTLE_AUTH", default="20/min"),
        "refresh": config("THROTTLE_REFRESH", default="60/min"),
        "write": config("THROTTLE_WRITE", default="60/min"),
        "vote": config("THROTTLE_VOTE", default="120/min"),
        # One ticket per (re)connect; generous enough for flaky networks and many tabs.
        "realtime_ticket": config("THROTTLE_REALTIME_TICKET", default="30/min"),
    },
    # Reverse proxies in front of Django. 0 = trust REMOTE_ADDR only; never the client's XFF.
    "NUM_PROXIES": config("NUM_PROXIES", default=0, cast=int),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        seconds=config("JWT_ACCESS_LIFETIME", default=900, cast=int)
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        seconds=config("JWT_REFRESH_LIFETIME", default=604800, cast=int)
    ),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    # Tokens embed a password-hash claim; any password change invalidates older tokens.
    "CHECK_REVOKE_TOKEN": True,
}

# The refresh token lives in an HttpOnly cookie scoped to the auth endpoints, so XSS can't read it.
AUTH_REFRESH_COOKIE = {
    "key": "nexus_refresh",
    "path": "/api/v1/auth/",
    "samesite": "Strict",
    "secure": config("AUTH_COOKIE_SECURE", default=not DEBUG, cast=bool),
}
# The SPA's dev server is another origin; the refresh cookie must travel with its auth calls.
CORS_ALLOW_CREDENTIALS = True

CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:5173,http://127.0.0.1:5173",
    cast=Csv(),
)

AUTH_USER_MODEL = "users.User"

# Base URL of the SPA, used to build links in outgoing emails and OG tags.
FRONTEND_URL = config("FRONTEND_URL", default="http://localhost:5173")

# Email — console backend by default; point at SMTP via env in production.
EMAIL_BACKEND = config("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = config("EMAIL_HOST", default="localhost")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_TIMEOUT = config("EMAIL_TIMEOUT", default=30, cast=float)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="Nexus <noreply@localhost>")

# ─── Realtime (WebSocket) ──────────────────────
# Off without REDIS_URL: the API and the realtime service must share the channel layer and the
# ticket cache. Clients then keep polling, so nothing breaks.
REDIS_URL = config("REDIS_URL", default="")
CHANNEL_LAYERS = channel_layers(REDIS_URL, db=config("REALTIME_REDIS_DB", default=2, cast=int))
REALTIME_ALLOWED_ORIGINS = websocket_origins(FRONTEND_URL, [])
# Seconds a one-time socket ticket stays valid.
REALTIME_TICKET_TTL = 30
# Seconds an accepted socket may stay unauthenticated.
REALTIME_AUTH_TIMEOUT = 5.0
# Seconds between the server's own re-checks of an open socket's user (active, same password,
# not logged out). Every event is checked as well; client pings play no part in it.
REALTIME_REVALIDATE_INTERVAL = 60.0
# Admission limits (apps/realtime/admission.py). Sockets waiting for their auth frame, per
# realtime process; nginx also caps sockets per client address and in total.
REALTIME_MAX_PENDING_SOCKETS = config("REALTIME_MAX_PENDING_SOCKETS", default=256, cast=int)
# Open sockets per user across all processes (one per tab, several devices).
REALTIME_MAX_SOCKETS_PER_USER = config("REALTIME_MAX_SOCKETS_PER_USER", default=10, cast=int)
# Where the per-user slots live; shared by every realtime process. Empty = in-process only.
REALTIME_SLOT_REDIS_URL = REDIS_URL
# A connection slot lapses this long after its socket's last server-side refresh (crashed process).
REALTIME_SLOT_TTL = 3 * REALTIME_REVALIDATE_INTERVAL
# Upper bound on releasing a closing socket's group membership and slot; what is left lapses.
REALTIME_CLEANUP_TIMEOUT = 2.0
# Upper bound on a publish from a request; a slow Redis must not hold the response.
REALTIME_PUBLISH_TIMEOUT = 1.0

# PostgreSQL queue shared by the API and db_worker; tasks do not go through Redis.
TASKS = {
    "default": {
        "BACKEND": "django_tasks_db.DatabaseBackend",
        "QUEUES": ["default"],
    }
}

"""Media storage settings: local filesystem (default) or an S3-compatible bucket behind a CDN.

Kept free of Django imports other than ImproperlyConfigured so settings can use it at import time.
"""

import ipaddress
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

# Keys are random UUIDs and never rewritten, but objects do get deleted (account erasure, replaced
# avatars). A short lifetime bounds how long a deleted file can linger on CDN edges; purge the CDN
# for urgent takedowns (see the README).
MEDIA_CACHE_CONTROL = "public, max-age=86400"

_METADATA_HOSTS = {"metadata.google.internal", "metadata"}


def validate_http_url(name: str, value: str, *, allow_path: bool = False) -> str:
    """Accept only a plain http(s) origin: no credentials, query, fragment, or metadata hosts.

    The endpoint comes from operator configuration, never from users, but a mistyped or injected
    value must not point the server at local files or the cloud metadata service (SSRF), and
    a CDN origin must stay a single exact origin so the CSP cannot be widened through it.
    """
    value = (value or "").strip()
    if any(ch in value for ch in "\r\n\t ;,*"):
        raise ImproperlyConfigured(
            f"{name} must be a single http(s) URL without spaces or wildcards."
        )
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ImproperlyConfigured(f"{name} must be an http(s) URL with a host.")
    if parts.username or parts.password:
        raise ImproperlyConfigured(f"{name} must not contain credentials.")
    if parts.query or parts.fragment:
        raise ImproperlyConfigured(f"{name} must not contain a query string or fragment.")
    if not allow_path and parts.path not in ("", "/"):
        raise ImproperlyConfigured(f"{name} must not contain a path.")
    host = parts.hostname.lower()
    if host in _METADATA_HOSTS:
        raise ImproperlyConfigured(f"{name} must not point at a cloud metadata host.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and (
        address.is_link_local or address.is_unspecified or address.is_multicast
    ):
        raise ImproperlyConfigured(f"{name} must not point at a link-local or unspecified address.")
    return value.rstrip("/")


def build_media_storage(get) -> dict:
    """The STORAGES["default"] entry. `get(name, default="")` reads one setting as a string."""
    backend = get("STORAGE_BACKEND", "filesystem").strip().lower()
    if backend == "filesystem":
        return {"BACKEND": "django.core.files.storage.FileSystemStorage"}
    if backend != "s3":
        raise ImproperlyConfigured("STORAGE_BACKEND must be 'filesystem' or 's3'.")

    bucket = get("S3_BUCKET").strip()
    if not bucket:
        raise ImproperlyConfigured("S3_BUCKET is required when STORAGE_BACKEND=s3.")
    options = {
        "bucket_name": bucket,
        # Unset keys fall back to boto's credential chain (instance roles and the like).
        "access_key": get("AWS_ACCESS_KEY_ID") or None,
        "secret_key": get("AWS_SECRET_ACCESS_KEY") or None,
        "region_name": get("AWS_S3_REGION_NAME") or None,
        "addressing_style": get("S3_ADDRESSING_STYLE", "auto"),
        "signature_version": "s3v4",
        # Immutable keys: never overwrite, never hand out expiring signed URLs, no per-object ACLs
        # (R2 has none); public read is a bucket policy, see the README.
        "file_overwrite": False,
        "querystring_auth": False,
        "default_acl": None,
        "object_parameters": {"CacheControl": MEDIA_CACHE_CONTROL},
    }
    endpoint = get("S3_ENDPOINT_URL").strip()
    if endpoint:
        options["endpoint_url"] = validate_http_url("S3_ENDPOINT_URL", endpoint)
    base_url = get("MEDIA_BASE_URL").strip()
    if base_url:
        base = validate_http_url("MEDIA_BASE_URL", base_url, allow_path=True)
        parts = urlsplit(base)
        options["custom_domain"] = parts.netloc + parts.path
        options["url_protocol"] = f"{parts.scheme}:"
    return {"BACKEND": "apps.common.storage.MediaS3Storage", "OPTIONS": options}


def require_https_media(storage: dict) -> None:
    """Production guard: a plain-http public media URL would mix content and expose users."""
    if storage.get("OPTIONS", {}).get("url_protocol") == "http:":
        raise ImproperlyConfigured("MEDIA_BASE_URL must use https in production.")

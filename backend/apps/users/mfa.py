"""Two-factor authentication primitives: TOTP (RFC 6238), encrypted secrets, recovery codes.

Threat model, in short (details live in the commit message):
- the TOTP secret is stored Fernet-encrypted; without a usable MFA_ENCRYPTION_KEY the feature is
  off and anything that would need the secret fails closed (never "skip the second factor");
- a code is accepted once: the matched time step is recorded and must increase;
- online guessing is capped per user (5 failures / 15 min) regardless of challenge or IP;
- recovery codes are random, single use and stored hashed.
"""

import base64
import hashlib
import hmac
import logging
import re
import secrets
import struct
import time
from datetime import timedelta
from urllib.parse import quote

import segno
from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import Throttled
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from .models import MfaChallenge, MfaDevice, MfaFailure, MfaRecoveryCode, User

logger = logging.getLogger(__name__)

STEP_SECONDS = 30
DIGITS = 6
CHALLENGE_TTL_SECONDS = 300
CHALLENGE_MAX_ATTEMPTS = 5
LOCKOUT_FAILURES = 5
LOCKOUT_WINDOW = timedelta(minutes=15)
RECOVERY_CODE_COUNT = 10
_RECOVERY_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O/1/I/L lookalikes
_RECOVERY_LENGTH = 10
_CHALLENGE_SALT = "nexus.mfa.challenge"


class MfaUnavailable(Exception):
    """No usable encryption key: the feature is off and must not be bypassed."""


# ── encryption ────────────────────────────────────────────────────────────────


def _cipher() -> MultiFernet:
    """Keys come from MFA_ENCRYPTION_KEY, comma separated; the first encrypts, all decrypt."""
    raw = [k.strip() for k in (settings.MFA_ENCRYPTION_KEY or "").split(",") if k.strip()]
    if not raw:
        raise MfaUnavailable("MFA_ENCRYPTION_KEY is not set.")
    try:
        return MultiFernet([Fernet(k.encode()) for k in raw])
    except (ValueError, TypeError) as exc:
        raise MfaUnavailable("MFA_ENCRYPTION_KEY is not a valid Fernet key list.") from exc


def mfa_available() -> bool:
    try:
        _cipher()
    except MfaUnavailable:
        return False
    return True


def encrypt_secret(secret: str) -> bytes:
    return _cipher().encrypt(secret.encode())


def decrypt_secret(token: bytes) -> str:
    try:
        return _cipher().decrypt(bytes(token)).decode()
    except InvalidToken as exc:
        raise MfaUnavailable("Stored secret cannot be decrypted with the configured keys.") from exc


def reencrypt_secret(token: bytes) -> bytes:
    """Re-encrypt under the first (newest) key; used by `rotate_mfa_keys`."""
    try:
        return _cipher().rotate(bytes(token))
    except InvalidToken as exc:
        raise MfaUnavailable("Stored secret cannot be decrypted with the configured keys.") from exc


# ── TOTP ──────────────────────────────────────────────────────────────────────


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _hotp(secret_b32: str, counter: int) -> str:
    padded = secret_b32 + "=" * (-len(secret_b32) % 8)
    digest = hmac.new(base64.b32decode(padded), struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10**DIGITS).zfill(DIGITS)


def totp(secret_b32: str, step: int) -> str:
    return _hotp(secret_b32, step)


def current_step() -> int:
    return int(time.time() // STEP_SECONDS)


def matching_step(secret_b32: str, code: str) -> int | None:
    """The time step (now ±1 for clock drift) the code belongs to, compared in constant time."""
    found = None
    now = current_step()
    for step in (now, now - 1, now + 1):
        if hmac.compare_digest(totp(secret_b32, step), code):
            found = step if found is None else found
    return found


def consume_step(device: MfaDevice, step: int) -> bool:
    """Record `step` as used; atomic, so two requests with the same code cannot both win."""
    return (
        MfaDevice.objects.filter(pk=device.pk, last_used_step__lt=step).update(last_used_step=step)
        == 1
    )


def provisioning_uri(username: str, secret_b32: str) -> str:
    issuer = settings.MFA_ISSUER
    label = quote(f"{issuer}:{username}")
    return (
        f"otpauth://totp/{label}?secret={secret_b32}&issuer={quote(issuer)}"
        f"&algorithm=SHA1&digits={DIGITS}&period={STEP_SECONDS}"
    )


def qr_data_uri(uri: str) -> str:
    return segno.make(uri, error="m").svg_data_uri(scale=5, border=2)


# ── recovery codes ────────────────────────────────────────────────────────────


def normalize_recovery(code: str) -> str:
    # ASCII only: Unicode letters/digits would otherwise reach the hashing code unchecked.
    return "".join(ch for ch in code.upper() if ch.isascii() and ch.isalnum())


def normalize_totp(code: str | None) -> str | None:
    """The six ASCII digits of a TOTP code (inner whitespace ignored), or None."""
    digits = re.sub(r"\s+", "", code or "")
    return digits if re.fullmatch(r"[0-9]{6}", digits) else None


def _lookup(normalized: str, key: str | None = None) -> str:
    """Keyed index value: finds the one candidate row so only one slow hash is checked."""
    key = (key if key is not None else settings.SECRET_KEY).encode()
    return hmac.new(key, b"mfa-recovery:" + normalized.encode(), hashlib.sha256).hexdigest()[:32]


def _lookups(normalized: str) -> list[str]:
    """Lookup values under the current SECRET_KEY and every fallback, so rotation keeps codes valid."""
    keys = [settings.SECRET_KEY, *getattr(settings, "SECRET_KEY_FALLBACKS", [])]
    return [_lookup(normalized, key) for key in keys]


def _new_recovery_code() -> str:
    raw = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(_RECOVERY_LENGTH))
    return f"{raw[:5]}-{raw[5:]}"


@transaction.atomic
def replace_recovery_codes(user) -> list[str]:
    """Delete every code and mint a fresh set; the plaintext is returned once and not stored."""
    MfaRecoveryCode.objects.filter(user=user).delete()
    codes = [_new_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
    MfaRecoveryCode.objects.bulk_create(
        MfaRecoveryCode(
            user=user,
            lookup=_lookup(normalize_recovery(code)),
            code_hash=make_password(normalize_recovery(code)),
        )
        for code in codes
    )
    return codes


def consume_recovery_code(user, code: str) -> bool:
    normalized = normalize_recovery(code)
    if len(normalized) != _RECOVERY_LENGTH:
        return False
    row = MfaRecoveryCode.objects.filter(
        user=user, lookup__in=_lookups(normalized), used_at__isnull=True
    ).first()
    if row is None or not check_password(normalized, row.code_hash):
        return False
    return (
        MfaRecoveryCode.objects.filter(pk=row.pk, used_at__isnull=True).update(
            used_at=timezone.now()
        )
        == 1
    )


def recovery_codes_remaining(user) -> int:
    return MfaRecoveryCode.objects.filter(user=user, used_at__isnull=True).count()


# ── failure limiter ───────────────────────────────────────────────────────────


def is_locked(user) -> bool:
    since = timezone.now() - LOCKOUT_WINDOW
    return MfaFailure.objects.filter(user=user, created__gte=since).count() >= LOCKOUT_FAILURES


def record_failure(user, ip: str | None, kind: str) -> None:
    MfaFailure.objects.create(user=user, ip=ip or None, kind=kind)
    # The table only needs the lockout window; keep it from growing without bound.
    MfaFailure.objects.filter(user=user, created__lt=timezone.now() - timedelta(days=1)).delete()
    logger.warning("MFA %s failure for user %s from %s", kind, user.pk, ip)


def guarded_attempt(user, ip: str | None, kind: str, check) -> str | None:
    """Run one second-factor attempt under a per-user lock.

    `check()` returns the method name on success or None. The lock serialises every attempt of
    the user, so the lockout count is read and extended without a race: parallel requests queue
    here and cannot slip extra guesses in before the failures are recorded. Raises Throttled while
    the user is locked out (even a correct code is refused then).
    """
    with transaction.atomic():
        User.objects.select_for_update().get(pk=user.pk)
        if is_locked(user):
            raise Throttled(detail="Too many failed attempts. Try again later.")
        method = check()
        if method is None:
            record_failure(user, ip, kind)
    return method


def verify_second_factor(user, code: str, *, ip: str | None, kind: str) -> str | None:
    """Check a TOTP or recovery code for `user`. Returns "totp"/"recovery", or None on failure.

    Without a usable MFA_ENCRYPTION_KEY the TOTP secret cannot be read, so only recovery codes
    (which are hashed, not encrypted) can pass: the factor is never skipped.
    """

    def check() -> str | None:
        digits = normalize_totp(code)
        if digits is not None:
            device = MfaDevice.objects.filter(user=user, confirmed_at__isnull=False).first()
            if device is None:
                return None
            try:
                secret = decrypt_secret(device.secret_encrypted)
            except MfaUnavailable:
                # nosemgrep: python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure -- logs only user.pk, never the secret
                logger.error(
                    "MFA secret of user %s cannot be decrypted; recovery codes only", user.pk
                )
                return None
            step = matching_step(secret, digits)
            return "totp" if step is not None and consume_step(device, step) else None
        return "recovery" if consume_recovery_code(user, code or "") else None

    return guarded_attempt(user, ip, kind, check)


# ── login challenge ───────────────────────────────────────────────────────────


def fingerprint(user) -> str:
    from rest_framework_simplejwt.utils import get_md5_hash_password

    return get_md5_hash_password(user.password)


def create_challenge(user) -> str:
    """A signed, 5-minute, single-use token proving the password step succeeded."""
    from django.core import signing

    # Expired challenges are useless; keep the table from growing.
    MfaChallenge.objects.filter(
        user=user, expires_at__lt=timezone.now() - timedelta(days=1)
    ).delete()
    challenge = MfaChallenge.objects.create(
        user=user,
        expires_at=timezone.now() + timedelta(seconds=CHALLENGE_TTL_SECONDS),
        fingerprint=fingerprint(user),
    )
    return signing.dumps({"c": str(challenge.pk), "u": user.pk}, salt=_CHALLENGE_SALT)


def load_challenge(token: str) -> MfaChallenge | None:
    """The live challenge behind `token`, or None for anything wrong with it (no detail leaked)."""
    from django.core import signing

    try:
        payload = signing.loads(token, salt=_CHALLENGE_SALT, max_age=CHALLENGE_TTL_SECONDS)
        challenge = MfaChallenge.objects.select_related("user").get(
            pk=payload["c"], user_id=payload["u"]
        )
    except (signing.BadSignature, MfaChallenge.DoesNotExist, KeyError, TypeError, ValueError):
        return None
    user = challenge.user
    if (
        challenge.consumed_at is not None
        or challenge.expires_at <= timezone.now()
        or challenge.attempts >= CHALLENGE_MAX_ATTEMPTS
        or not user.is_active
        or challenge.fingerprint != fingerprint(user)
    ):
        return None
    return challenge


def reserve_attempt(challenge: MfaChallenge) -> bool:
    """Claim one of the challenge's attempts before checking the code (check-and-increment in
    a single UPDATE, so parallel requests cannot exceed the cap)."""
    return (
        MfaChallenge.objects.filter(
            pk=challenge.pk,
            consumed_at__isnull=True,
            attempts__lt=CHALLENGE_MAX_ATTEMPTS,
            expires_at__gt=timezone.now(),
        ).update(attempts=F("attempts") + 1)
        == 1
    )


def consume_challenge(challenge: MfaChallenge) -> bool:
    return (
        MfaChallenge.objects.filter(pk=challenge.pk, consumed_at__isnull=True).update(
            consumed_at=timezone.now()
        )
        == 1
    )


# ── session revocation ────────────────────────────────────────────────────────


def revoke_all_sessions(user) -> None:
    """Blacklist every outstanding refresh token and close every realtime socket of the user."""
    from apps.push.services import drop_subscriptions

    from .services import end_realtime_sessions

    live = OutstandingToken.objects.filter(user=user, blacklistedtoken__isnull=True)
    BlacklistedToken.objects.bulk_create(
        [BlacklistedToken(token_id=pk) for pk in live.values_list("pk", flat=True)],
        ignore_conflicts=True,
    )
    # Tokens carry this generation; bumping it kills access tokens at once and closes the window
    # where a refresh token slips in between the sweep above and the next request.
    User.objects.filter(pk=user.pk).update(auth_generation=F("auth_generation") + 1)
    user.refresh_from_db(fields=["auth_generation"])
    end_realtime_sessions(user.pk)
    drop_subscriptions(user)

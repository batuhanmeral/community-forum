"""Review fixes for two-factor authentication: atomic limits, admin, recovery, generations."""

import io
import threading

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import Client
from rest_framework.exceptions import Throttled
from rest_framework.test import APIClient

from apps.users import mfa
from apps.users.models import MfaChallenge, MfaDevice, MfaFailure, MfaRecoveryCode
from apps.users.tests import test_mfa as base
from apps.users.tests.test_mfa import ME, PASSWORD, challenge_token, enrol, login, verify

# Fixtures shared with the main MFA module (the autouse key fixture comes along).
mfa_key = base.mfa_key
user = base.user
clock = base.clock

User = get_user_model()


# ── #2 attempts are reserved atomically ───────────────────────────────────────


def _run_parallel(count, target):
    from django.db import connection

    def wrapper(i):
        try:
            target(i)
        finally:
            connection.close()

    threads = [threading.Thread(target=wrapper, args=(i,)) for i in range(count)]
    [t.start() for t in threads]
    [t.join() for t in threads]


@pytest.mark.django_db(transaction=True)
def test_parallel_guesses_cannot_exceed_the_per_user_limit(user, clock):
    enrol(user, clock)
    outcomes = []

    def guess(_):
        try:
            outcomes.append(mfa.verify_second_factor(user, "000000", ip=None, kind="verify"))
        except Throttled:
            outcomes.append("throttled")

    _run_parallel(16, guess)
    assert MfaFailure.objects.filter(user=user).count() == mfa.LOCKOUT_FAILURES
    assert outcomes.count("throttled") == 16 - mfa.LOCKOUT_FAILURES
    assert outcomes.count(None) == mfa.LOCKOUT_FAILURES


@pytest.mark.django_db(transaction=True)
def test_parallel_attempts_cannot_exceed_the_per_challenge_cap(user, clock):
    enrol(user, clock)
    challenge = MfaChallenge.objects.create(
        user=user,
        expires_at=mfa.timezone.now() + mfa.timedelta(minutes=5),
        fingerprint=mfa.fingerprint(user),
    )
    wins = []
    _run_parallel(16, lambda _: wins.append(mfa.reserve_attempt(challenge)))
    assert wins.count(True) == mfa.CHALLENGE_MAX_ATTEMPTS
    assert MfaChallenge.objects.get(pk=challenge.pk).attempts == mfa.CHALLENGE_MAX_ATTEMPTS


@pytest.mark.django_db(transaction=True)
def test_parallel_requests_with_one_token_make_at_most_five_guesses(user, clock):
    enrol(user, clock)
    token = challenge_token(user)
    statuses = []
    _run_parallel(12, lambda _: statuses.append(verify(APIClient(), token, "000000").status_code))
    assert MfaFailure.objects.filter(user=user).count() <= mfa.CHALLENGE_MAX_ATTEMPTS
    # 401 for refused guesses; 429 once the per-IP throttle also kicks in.
    assert set(statuses) <= {401, 429} and statuses.count(401) >= 5


# ── #7 digits and spaces ──────────────────────────────────────────────────────


@pytest.mark.django_db
@pytest.mark.parametrize("code", ["²²²²²²", "١٢٣٤٥٦", "１２３４５６", "12345"])
def test_non_ascii_or_malformed_codes_are_a_clean_failure_not_a_500(user, clock, code):
    enrol(user, clock)
    resp = verify(APIClient(), challenge_token(user), code)
    assert resp.status_code == 401
    api = APIClient()
    api.force_authenticate(user)
    secret = MfaDevice.objects.get(user=user)  # already enabled: use the disable endpoint
    assert secret
    bad = api.post(ME + "disable/", {"password": PASSWORD, "code": code}, format="json")
    assert bad.status_code == 400


@pytest.mark.django_db
def test_confirm_rejects_non_ascii_digits_cleanly(user):
    api = APIClient()
    api.force_authenticate(user)
    api.post(ME + "setup/", {"password": PASSWORD}, format="json")
    assert api.post(ME + "confirm/", {"code": "١٢٣٤٥٦"}, format="json").status_code == 400


@pytest.mark.django_db
def test_spaces_inside_the_code_are_accepted_everywhere(user, clock):
    secret, _ = enrol(user, clock)
    clock["step"] += 1
    code = mfa.totp(secret, clock["step"])
    spaced = f"{code[:3]} {code[3:]}"
    assert verify(APIClient(), challenge_token(user), spaced).status_code == 200
    api = APIClient()
    api.force_authenticate(user)
    clock["step"] += 1
    spaced = mfa.totp(secret, clock["step"])
    spaced = f" {spaced[:3]} {spaced[3:]} "
    resp = api.post(ME + "disable/", {"password": PASSWORD, "code": spaced}, format="json")
    assert resp.status_code == 200


# ── #6 SECRET_KEY rotation ────────────────────────────────────────────────────


@pytest.mark.django_db
def test_recovery_codes_survive_a_secret_key_rotation(user, clock, settings):
    _, codes = enrol(user, clock)
    old_key = settings.SECRET_KEY
    settings.SECRET_KEY = "a-completely-new-secret-key-for-the-rotation-test-0123456789"
    settings.SECRET_KEY_FALLBACKS = [old_key]
    first = verify(APIClient(), challenge_token(user), codes[0])
    assert first.status_code == 200
    # Used code is spent, and an unrelated key still fails.
    assert verify(APIClient(), challenge_token(user), codes[0]).status_code == 401
    settings.SECRET_KEY_FALLBACKS = []
    assert verify(APIClient(), challenge_token(user), codes[1]).status_code == 401


# ── #4 recovery without the encryption key, reset command ─────────────────────


@pytest.mark.django_db
def test_without_the_key_login_still_issues_a_challenge_but_only_recovery_codes_work(
    user, clock, settings
):
    secret, codes = enrol(user, clock)
    settings.MFA_ENCRYPTION_KEY = ""
    resp = login(APIClient())
    assert resp.status_code == 200 and resp.data["mfa_required"] is True
    assert "access" not in resp.data
    token = resp.data["mfa_token"]
    clock["step"] += 1
    refused = verify(APIClient(), token, mfa.totp(secret, clock["step"]))
    assert refused.status_code == 401 and refused.data == {
        "detail": "Invalid or expired verification."
    }
    ok = verify(APIClient(), challenge_token(user), codes[0])
    assert ok.status_code == 200 and ok.data["access"]


@pytest.mark.django_db
def test_reset_mfa_for_one_user(user, clock):
    other = User.objects.create_user(username="bob", email="b@example.test", password=PASSWORD)
    enrol(user, clock)
    enrol(other, clock)
    stolen = APIClient()
    login_after = verify(stolen, challenge_token(user), enrol_codes(user))
    assert login_after.status_code == 200
    out = io.StringIO()
    call_command("reset_mfa", user="alice", stdout=out)
    assert not MfaDevice.objects.filter(user=user).exists()
    assert not MfaRecoveryCode.objects.filter(user=user).exists()
    assert MfaDevice.objects.filter(user=other).exists()
    assert stolen.post("/api/v1/auth/refresh/").status_code == 401  # sessions revoked
    assert "mfa_required" not in login(APIClient()).data


def enrol_codes(user):
    """A fresh recovery code for `user` (the API only hands them out once)."""
    return mfa.replace_recovery_codes(user)[0]


@pytest.mark.django_db
def test_reset_mfa_all_needs_confirmation(user, clock):
    enrol(user, clock)
    with pytest.raises(CommandError):
        call_command("reset_mfa", all=True)
    with pytest.raises(CommandError):
        call_command("reset_mfa")
    with pytest.raises(CommandError):
        call_command("reset_mfa", user="nobody")
    assert MfaDevice.objects.filter(user=user).exists()
    call_command("reset_mfa", all=True, yes=True, stdout=io.StringIO())
    assert not MfaDevice.objects.exists()


# ── #5 auth generation ────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_access_tokens_die_immediately_on_an_mfa_change(user, clock):
    api = APIClient()
    resp = login(api)
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")
    assert api.get(ME).status_code == 200
    enrol(user, clock)  # revokes every session
    assert api.get(ME).status_code == 401


@pytest.mark.django_db
def test_a_refresh_token_minted_before_the_bump_is_refused_even_if_not_blacklisted(user, clock):
    from apps.users.tokens import NexusRefreshToken

    stale = NexusRefreshToken.for_user(user)
    enrol(user, clock)
    # Simulate the race: the token slipped in after the blacklist sweep.
    api = APIClient()
    api.cookies["nexus_refresh"] = str(stale)
    assert api.post("/api/v1/auth/refresh/").status_code == 401


@pytest.mark.django_db
def test_fresh_session_after_a_change_works(user, clock):
    secret, _ = enrol(user, clock)
    api = APIClient()
    clock["step"] += 1
    resp = verify(api, challenge_token(user), mfa.totp(secret, clock["step"]))
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")
    assert api.get(ME).status_code == 200
    assert api.post("/api/v1/auth/refresh/").status_code == 200


# ── #3 Django admin ───────────────────────────────────────────────────────────


@pytest.fixture
def staff(db):
    return User.objects.create_user(
        username="boss",
        email="boss@example.test",
        password=PASSWORD,
        is_staff=True,
        is_superuser=True,
    )


def admin_login(client, username="boss", otp=None):
    data = {"username": username, "password": PASSWORD, "next": "/admin/"}
    if otp is not None:
        data["otp"] = otp
    return client.post("/admin/login/", data)


@pytest.mark.django_db
def test_admin_login_demands_the_second_factor_for_staff_with_a_device(staff, clock):
    secret, codes = enrol(staff, clock)
    client = Client()
    no_code = admin_login(client)
    assert no_code.status_code == 200 and "_auth_user_id" not in client.session
    assert admin_login(client, otp="000000").status_code == 200
    assert "_auth_user_id" not in client.session
    clock["step"] += 1
    ok = admin_login(client, otp=mfa.totp(secret, clock["step"]))
    assert ok.status_code == 302 and "_auth_user_id" in client.session


@pytest.mark.django_db
def test_admin_login_accepts_a_recovery_code_and_is_rate_limited(staff, clock):
    _, codes = enrol(staff, clock)
    client = Client()
    assert admin_login(client, otp=codes[0]).status_code == 302
    locked = Client()
    for _ in range(mfa.LOCKOUT_FAILURES):
        admin_login(locked, otp="000000")
    assert "_auth_user_id" not in locked.session
    assert MfaFailure.objects.filter(user=staff, kind="admin").count() == mfa.LOCKOUT_FAILURES
    right = admin_login(locked, otp=codes[1])
    assert right.status_code == 200 and "_auth_user_id" not in locked.session


@pytest.mark.django_db
def test_staff_without_a_device_log_in_as_before(staff):
    client = Client()
    assert admin_login(client).status_code == 302 and "_auth_user_id" in client.session


@pytest.mark.django_db
def test_admin_is_mounted_only_when_enabled():
    from config.urls import admin_patterns

    assert admin_patterns(False) == []
    assert [str(p.pattern) for p in admin_patterns(True)] == ["admin/"]


def test_production_defaults_to_no_admin():
    import os
    import subprocess
    import sys

    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings.prod",
        "SECRET_KEY": "x" * 60,
        "ALLOWED_HOSTS": "example.com",
        "CSRF_TRUSTED_ORIGINS": "https://example.com",
        "FRONTEND_URL": "https://example.com",
    }
    env.pop("ADMIN_ENABLED", None)
    out = subprocess.run(
        [sys.executable, "-c", "from django.conf import settings; print(settings.ADMIN_ENABLED)"],
        capture_output=True,
        text=True,
        env=env,
        cwd=os.getcwd(),
    )
    assert out.stdout.strip() == "False", out.stderr

"""Two-factor authentication: TOTP, recovery codes and the abuse cases of the threat model."""

import base64
from datetime import timedelta

import pytest
from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.users import mfa
from apps.users.models import MfaChallenge, MfaDevice, MfaFailure, MfaRecoveryCode

User = get_user_model()
PASSWORD = "StrongPass123!"
LOGIN = "/api/v1/auth/login/"
VERIFY = "/api/v1/auth/mfa/verify/"
ME = "/api/v1/users/me/mfa/"
GENERIC = {"detail": "Invalid or expired verification."}

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def mfa_key(settings):
    settings.MFA_ENCRYPTION_KEY = Fernet.generate_key().decode()
    # Enrolment hashes ten recovery codes; PBKDF2 would make this module needlessly slow.
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture
def user():
    return User.objects.create_user(username="alice", email="alice@example.com", password=PASSWORD)


@pytest.fixture
def clock(monkeypatch):
    """Controllable TOTP time step."""
    state = {"step": 1_000_000}
    monkeypatch.setattr(mfa, "current_step", lambda: state["step"])
    return state


def login(api, username="alice", password=PASSWORD):
    return api.post(LOGIN, {"username": username, "password": password}, format="json")


def enrol(user, clock):
    """Enable MFA for `user` through the API; returns (secret, recovery_codes, step)."""
    api = APIClient()
    api.force_authenticate(user)
    secret = api.post(ME + "setup/", {"password": PASSWORD}, format="json").data["secret"]
    clock["step"] += 1
    step = clock["step"]
    resp = api.post(ME + "confirm/", {"code": mfa.totp(secret, step)}, format="json")
    assert resp.status_code == 200, resp.data
    return secret, resp.data["recovery_codes"]


def challenge_token(user):
    api = APIClient()
    resp = login(api)
    assert resp.status_code == 200 and resp.data["mfa_required"] is True
    return resp.data["mfa_token"]


def verify(api, token, code):
    return api.post(VERIFY, {"mfa_token": token, "code": code}, format="json")


# ── primitives ────────────────────────────────────────────────────────────────


def test_totp_matches_rfc_6238_vectors():
    secret = base64.b32encode(b"12345678901234567890").decode()
    assert mfa.totp(secret, 59 // 30) == "287082"
    assert mfa.totp(secret, 1111111109 // 30) == "081804"
    assert mfa.totp(secret, 20000000000 // 30) == "353130"


def test_secret_is_encrypted_at_rest(user, clock):
    secret, _ = enrol(user, clock)
    raw = bytes(MfaDevice.objects.get(user=user).secret_encrypted)
    assert secret.encode() not in raw
    assert mfa.decrypt_secret(raw) == secret


def test_recovery_codes_are_hashed(user, clock):
    _, codes = enrol(user, clock)
    assert len(codes) == 10 and len(set(codes)) == 10
    stored = list(MfaRecoveryCode.objects.filter(user=user).values_list("code_hash", flat=True))
    assert len(stored) == 10
    assert not any(code in h or code.replace("-", "") in h for h in stored for code in codes)


# ── availability ──────────────────────────────────────────────────────────────


def test_feature_is_off_without_a_key_and_says_so(user, settings):
    settings.MFA_ENCRYPTION_KEY = ""
    api = APIClient()
    api.force_authenticate(user)
    assert api.get(ME).data == {"available": False, "enabled": False, "recovery_codes_remaining": 0}
    resp = api.post(ME + "setup/", {"password": PASSWORD}, format="json")
    assert resp.status_code == 503
    assert not MfaDevice.objects.exists()


def test_invalid_key_is_rejected_loudly(user, settings):
    settings.MFA_ENCRYPTION_KEY = "not-a-fernet-key"
    api = APIClient()
    api.force_authenticate(user)
    assert api.post(ME + "setup/", {"password": PASSWORD}, format="json").status_code == 503


def test_login_never_skips_the_factor_when_the_key_disappears(user, clock, settings):
    enrol(user, clock)
    settings.MFA_ENCRYPTION_KEY = ""
    resp = login(APIClient())
    # Still a challenge (recovery codes need no key); never a session.
    assert resp.status_code == 200 and resp.data["mfa_required"] is True
    assert "access" not in resp.data and "nexus_refresh" not in resp.cookies


# ── enrolment ─────────────────────────────────────────────────────────────────


def test_setup_needs_the_password(user):
    api = APIClient()
    api.force_authenticate(user)
    assert api.post(ME + "setup/", {"password": "wrong"}, format="json").status_code == 400
    assert api.post(ME + "setup/", {}, format="json").status_code == 400
    assert not MfaDevice.objects.exists()


def test_setup_returns_uri_and_qr_but_does_not_enable(user):
    api = APIClient()
    api.force_authenticate(user)
    resp = api.post(ME + "setup/", {"password": PASSWORD}, format="json")
    assert resp.status_code == 200
    assert resp.data["otpauth_uri"].startswith("otpauth://totp/")
    assert resp.data["secret"] in resp.data["otpauth_uri"]
    assert resp.data["qr_data_uri"].startswith("data:image/svg+xml")
    assert api.get(ME).data["enabled"] is False
    assert "mfa_required" not in login(APIClient()).data  # pending secret does not gate login


def test_confirm_with_a_wrong_code_does_not_enable(user, clock):
    api = APIClient()
    api.force_authenticate(user)
    api.post(ME + "setup/", {"password": PASSWORD}, format="json")
    assert api.post(ME + "confirm/", {"code": "000000"}, format="json").status_code == 400
    assert api.get(ME).data["enabled"] is False
    assert MfaFailure.objects.filter(user=user).count() == 1


def test_confirm_enables_and_hands_out_a_fresh_session(user, clock):
    api = APIClient()
    api.force_authenticate(user)
    secret = api.post(ME + "setup/", {"password": PASSWORD}, format="json").data["secret"]
    clock["step"] += 1
    resp = api.post(ME + "confirm/", {"code": mfa.totp(secret, clock["step"])}, format="json")
    assert resp.status_code == 200
    assert resp.data["access"] and "refresh" not in resp.data
    assert "nexus_refresh" in resp.cookies
    assert api.get(ME).data == {"available": True, "enabled": True, "recovery_codes_remaining": 10}


def test_setup_is_refused_once_enabled(user, clock):
    enrol(user, clock)
    api = APIClient()
    api.force_authenticate(user)
    assert api.post(ME + "setup/", {"password": PASSWORD}, format="json").status_code == 409


# ── login ─────────────────────────────────────────────────────────────────────


def test_password_alone_never_yields_a_session(user, clock):
    enrol(user, clock)
    resp = login(APIClient())
    assert resp.status_code == 200
    assert set(resp.data) == {"mfa_required", "mfa_token"}
    assert "nexus_refresh" not in resp.cookies


def test_wrong_password_looks_identical_for_mfa_plain_and_unknown_users(user, clock):
    other = User.objects.create_user(username="bob", email="b@example.com", password=PASSWORD)
    enrol(user, clock)
    bodies = [
        login(APIClient(), "alice", "bad"),
        login(APIClient(), "bob", "bad"),
        login(APIClient(), "nobody", "bad"),
    ]
    assert {r.status_code for r in bodies} == {401}
    assert bodies[0].data == bodies[1].data == bodies[2].data
    assert other


def test_verify_with_totp_issues_the_session(user, clock):
    secret, _ = enrol(user, clock)
    token = challenge_token(user)
    clock["step"] += 1
    api = APIClient()
    resp = verify(api, token, mfa.totp(secret, clock["step"]))
    assert resp.status_code == 200
    assert resp.data["access"] and "refresh" not in resp.data
    assert "nexus_refresh" in resp.cookies
    assert api.post("/api/v1/auth/refresh/").status_code == 200


def test_totp_code_cannot_be_replayed(user, clock):
    secret, _ = enrol(user, clock)
    clock["step"] += 1
    code = mfa.totp(secret, clock["step"])
    assert verify(APIClient(), challenge_token(user), code).status_code == 200
    replay = verify(APIClient(), challenge_token(user), code)
    assert replay.status_code == 401 and replay.data == GENERIC


def test_an_older_step_than_the_last_used_is_refused(user, clock):
    secret, _ = enrol(user, clock)
    clock["step"] += 1
    assert (
        verify(APIClient(), challenge_token(user), mfa.totp(secret, clock["step"])).status_code
        == 200
    )
    older = mfa.totp(secret, clock["step"] - 1)
    assert verify(APIClient(), challenge_token(user), older).status_code == 401


def test_adjacent_step_is_accepted_for_clock_drift(user, clock):
    secret, _ = enrol(user, clock)
    clock["step"] += 2
    previous = mfa.totp(secret, clock["step"] - 1)
    assert verify(APIClient(), challenge_token(user), previous).status_code == 200


def test_a_challenge_token_is_single_use(user, clock):
    secret, _ = enrol(user, clock)
    token = challenge_token(user)
    clock["step"] += 1
    assert verify(APIClient(), token, mfa.totp(secret, clock["step"])).status_code == 200
    clock["step"] += 1
    again = verify(APIClient(), token, mfa.totp(secret, clock["step"]))
    assert again.status_code == 401 and again.data == GENERIC


def test_expired_and_tampered_tokens_are_rejected_generically(user, clock, monkeypatch):
    secret, _ = enrol(user, clock)
    token = challenge_token(user)
    clock["step"] += 1
    code = mfa.totp(secret, clock["step"])
    tampered = token[:-2] + ("AA" if not token.endswith("AA") else "BB")
    for bad in (tampered, "garbage", ""):
        resp = verify(APIClient(), bad, code)
        assert resp.status_code == 401 and resp.data == GENERIC
    MfaChallenge.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
    expired = verify(APIClient(), token, code)
    assert expired.status_code == 401 and expired.data == GENERIC


def test_signed_timestamp_expiry_is_enforced(user, clock, monkeypatch):
    secret, _ = enrol(user, clock)
    token = challenge_token(user)
    real = signing.time.time
    monkeypatch.setattr(signing.time, "time", lambda: real() + mfa.CHALLENGE_TTL_SECONDS + 5)
    clock["step"] += 1
    assert verify(APIClient(), token, mfa.totp(secret, clock["step"])).status_code == 401


def test_challenge_is_dead_after_a_password_change(user, clock):
    secret, _ = enrol(user, clock)
    token = challenge_token(user)
    user.set_password("AnotherStrong456!")
    user.save()
    clock["step"] += 1
    assert verify(APIClient(), token, mfa.totp(secret, clock["step"])).status_code == 401


def test_inactive_user_gets_the_generic_failure(user, clock):
    secret, _ = enrol(user, clock)
    token = challenge_token(user)
    User.objects.filter(pk=user.pk).update(is_active=False)
    clock["step"] += 1
    resp = verify(APIClient(), token, mfa.totp(secret, clock["step"]))
    assert resp.status_code == 401 and resp.data == GENERIC


# ── brute force ───────────────────────────────────────────────────────────────


def test_five_failures_lock_the_user_even_for_the_right_code(user, clock):
    secret, _ = enrol(user, clock)
    api = APIClient()
    token = challenge_token(user)
    for _ in range(5):
        resp = verify(api, token, "000000")
        assert resp.status_code == 401 and resp.data == GENERIC
    assert MfaFailure.objects.filter(user=user).count() == 5
    clock["step"] += 1
    right = mfa.totp(secret, clock["step"])
    # The challenge itself is burnt after 5 attempts, even for the right code.
    assert verify(api, token, right).status_code == 401
    # A brand new challenge (fresh password login) is locked too: the limit is per user.
    assert verify(APIClient(), challenge_token(user), right).status_code == 429
    assert "nexus_refresh" not in api.cookies


def test_lockout_expires_after_the_window(user, clock):
    secret, _ = enrol(user, clock)
    token = challenge_token(user)
    for _ in range(5):
        verify(APIClient(), token, "000000")
    MfaFailure.objects.update(created=timezone.now() - timedelta(minutes=16))
    clock["step"] += 1
    assert (
        verify(APIClient(), challenge_token(user), mfa.totp(secret, clock["step"])).status_code
        == 200
    )


def test_failures_are_recorded_with_the_client_address(user, clock):
    enrol(user, clock)
    verify(APIClient(REMOTE_ADDR="203.0.113.9"), challenge_token(user), "123456")
    failure = MfaFailure.objects.get(user=user)
    assert failure.ip == "203.0.113.9" and failure.kind == "verify"


def test_verify_has_its_own_throttle_scope():
    from django.conf import settings

    from apps.users.views import MfaVerifyView

    assert MfaVerifyView.throttle_scope == "mfa"
    assert "mfa" in settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]


def test_verify_accepts_json_only(user, clock):
    enrol(user, clock)
    resp = APIClient().post(VERIFY, {"mfa_token": "x", "code": "1"})  # multipart form
    assert resp.status_code == 415


# ── recovery codes ────────────────────────────────────────────────────────────


def test_recovery_code_works_once(user, clock):
    _, codes = enrol(user, clock)
    first = verify(APIClient(), challenge_token(user), codes[0])
    assert first.status_code == 200 and first.data["recovery_codes_remaining"] == 9
    second = verify(APIClient(), challenge_token(user), codes[0])
    assert second.status_code == 401 and second.data == GENERIC
    assert MfaRecoveryCode.objects.filter(user=user, used_at__isnull=True).count() == 9


def test_recovery_code_is_forgiving_about_case_and_dashes(user, clock):
    _, codes = enrol(user, clock)
    sloppy = codes[3].replace("-", " ").lower()
    assert verify(APIClient(), challenge_token(user), sloppy).status_code == 200


def test_another_users_recovery_code_is_useless(user, clock):
    other = User.objects.create_user(username="bob", email="b@example.com", password=PASSWORD)
    _, mine = enrol(user, clock)
    enrol(other, clock)
    bob_token = APIClient().post(LOGIN, {"username": "bob", "password": PASSWORD}, format="json")
    assert verify(APIClient(), bob_token.data["mfa_token"], mine[0]).status_code == 401


# ── management ────────────────────────────────────────────────────────────────


def authed(user):
    api = APIClient()
    api.force_authenticate(user)
    return api


def test_disable_needs_password_and_a_valid_code(user, clock):
    secret, _ = enrol(user, clock)
    api = authed(user)
    clock["step"] += 1
    code = mfa.totp(secret, clock["step"])
    assert (
        api.post(ME + "disable/", {"password": "bad", "code": code}, format="json").status_code
        == 400
    )
    assert (
        api.post(
            ME + "disable/", {"password": PASSWORD, "code": "000000"}, format="json"
        ).status_code
        == 400
    )
    assert api.get(ME).data["enabled"] is True
    assert (
        api.post(ME + "disable/", {"password": PASSWORD, "code": code}, format="json").status_code
        == 200
    )
    assert not MfaDevice.objects.filter(user=user).exists()
    assert not MfaRecoveryCode.objects.filter(user=user).exists()
    assert "mfa_required" not in login(APIClient()).data


def test_disable_can_use_a_recovery_code(user, clock):
    _, codes = enrol(user, clock)
    resp = authed(user).post(
        ME + "disable/", {"password": PASSWORD, "code": codes[0]}, format="json"
    )
    assert resp.status_code == 200


def test_regenerate_replaces_every_code(user, clock):
    secret, old = enrol(user, clock)
    api = authed(user)
    clock["step"] += 1
    resp = api.post(
        ME + "recovery-codes/",
        {"password": PASSWORD, "code": mfa.totp(secret, clock["step"])},
        format="json",
    )
    assert resp.status_code == 200 and len(resp.data["recovery_codes"]) == 10
    assert verify(APIClient(), challenge_token(user), old[0]).status_code == 401
    assert (
        verify(APIClient(), challenge_token(user), resp.data["recovery_codes"][0]).status_code
        == 200
    )


def test_regenerate_without_a_valid_code_changes_nothing(user, clock):
    _, old = enrol(user, clock)
    resp = authed(user).post(
        ME + "recovery-codes/", {"password": PASSWORD, "code": "000000"}, format="json"
    )
    assert resp.status_code == 400
    assert verify(APIClient(), challenge_token(user), old[0]).status_code == 200


def test_management_endpoints_need_authentication():
    api = APIClient()
    for name in ("setup/", "confirm/", "disable/", "recovery-codes/"):
        assert api.post(ME + name, {}, format="json").status_code in (401, 403)
    assert api.get(ME).status_code in (401, 403)


# ── session revocation ────────────────────────────────────────────────────────


def _session(user, api):
    resp = login(api)
    assert resp.status_code == 200 and "access" in resp.data
    return api


def test_enabling_mfa_kills_other_sessions(user, clock):
    stolen = _session(user, APIClient())  # refresh cookie issued before MFA existed
    generation = User.objects.get(pk=user.pk).realtime_generation
    enrol(user, clock)
    assert stolen.post("/api/v1/auth/refresh/").status_code == 401
    assert User.objects.get(pk=user.pk).realtime_generation > generation


def test_disabling_and_regenerating_kill_other_sessions(user, clock):
    secret, codes = enrol(user, clock)
    other = APIClient()
    resp = verify(other, challenge_token(user), codes[0])
    assert resp.status_code == 200
    clock["step"] += 1
    generation = User.objects.get(pk=user.pk).realtime_generation
    authed(user).post(
        ME + "recovery-codes/",
        {"password": PASSWORD, "code": mfa.totp(secret, clock["step"])},
        format="json",
    )
    assert other.post("/api/v1/auth/refresh/").status_code == 401
    assert User.objects.get(pk=user.pk).realtime_generation > generation

    survivor = APIClient()
    clock["step"] += 1
    assert (
        verify(survivor, challenge_token(user), mfa.totp(secret, clock["step"])).status_code == 200
    )
    clock["step"] += 1
    authed(user).post(
        ME + "disable/",
        {"password": PASSWORD, "code": mfa.totp(secret, clock["step"])},
        format="json",
    )
    assert survivor.post("/api/v1/auth/refresh/").status_code == 401


def test_the_acting_session_keeps_working_via_the_fresh_cookie(user, clock):
    api = APIClient()
    login(api)
    api.force_authenticate(user)
    secret = api.post(ME + "setup/", {"password": PASSWORD}, format="json").data["secret"]
    clock["step"] += 1
    resp = api.post(ME + "confirm/", {"code": mfa.totp(secret, clock["step"])}, format="json")
    assert resp.status_code == 200
    api.cookies["nexus_refresh"] = resp.cookies["nexus_refresh"].value
    assert api.post("/api/v1/auth/refresh/").status_code == 200


# ── password reset must not bypass MFA ────────────────────────────────────────


def test_password_reset_does_not_bypass_mfa(user, clock):
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode

    enrol(user, clock)
    api = APIClient()
    resp = api.post(
        "/api/v1/auth/password-reset/confirm/",
        {
            "uid": urlsafe_base64_encode(force_bytes(user.pk)),
            "token": default_token_generator.make_token(user),
            "new_password": "BrandNewPass789!",
        },
        format="json",
    )
    assert resp.status_code == 204
    after = login(APIClient(), password="BrandNewPass789!")
    assert after.status_code == 200 and after.data["mfa_required"] is True
    assert "access" not in after.data and MfaDevice.objects.filter(user=user).exists()


# ── account lifecycle ─────────────────────────────────────────────────────────


def test_account_deletion_destroys_mfa_material(user, clock):
    from apps.users.services import delete_account

    enrol(user, clock)
    challenge_token(user)
    verify(APIClient(), "garbage", "000000")
    MfaFailure.objects.create(user=user, kind="verify")
    delete_account(user)
    assert not MfaDevice.objects.filter(user=user).exists()
    assert not MfaRecoveryCode.objects.filter(user=user).exists()
    assert not MfaChallenge.objects.filter(user=user).exists()
    assert not MfaFailure.objects.filter(user=user).exists()


def test_export_never_contains_mfa_secrets(user, clock):
    import json

    from apps.users.services import export_account

    secret, codes = enrol(user, clock)
    exported = json.dumps(export_account(user))
    assert secret not in exported and "secret" not in exported.lower()
    assert not any(code in exported for code in codes)


# ── key rotation ──────────────────────────────────────────────────────────────


def test_rotation_keeps_old_ciphertext_readable_and_reencrypts(user, clock, settings):
    secret, _ = enrol(user, clock)
    old_key = settings.MFA_ENCRYPTION_KEY
    new_key = Fernet.generate_key().decode()
    settings.MFA_ENCRYPTION_KEY = f"{new_key},{old_key}"
    assert mfa.decrypt_secret(bytes(MfaDevice.objects.get(user=user).secret_encrypted)) == secret
    call_command("rotate_mfa_keys", verbosity=0)
    settings.MFA_ENCRYPTION_KEY = new_key  # the old key can now be retired
    assert mfa.decrypt_secret(bytes(MfaDevice.objects.get(user=user).secret_encrypted)) == secret
    settings.MFA_ENCRYPTION_KEY = old_key
    with pytest.raises(mfa.MfaUnavailable):
        mfa.decrypt_secret(bytes(MfaDevice.objects.get(user=user).secret_encrypted))


def test_consuming_a_step_is_atomic(user, clock):
    enrol(user, clock)
    device = MfaDevice.objects.get(user=user)
    assert mfa.consume_step(device, clock["step"] + 5) is True
    assert mfa.consume_step(device, clock["step"] + 5) is False
    assert mfa.consume_step(device, clock["step"] + 4) is False

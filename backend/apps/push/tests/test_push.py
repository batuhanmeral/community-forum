"""Web push: endpoint allowlist (SSRF), minimal payloads, preferences, cleanup and abuse cases."""

import base64
import io
import json
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.contrib.auth import get_user_model
from django.core.management import call_command
from pywebpush import WebPushException
from rest_framework.test import APIClient

from apps.messaging.models import Conversation, Message
from apps.notifications.services import notify
from apps.push import sender, vapid
from apps.push.models import PushPreference, PushSubscription
from apps.push.validators import validate_endpoint, validate_keys
from apps.social.models import Block

pytestmark = pytest.mark.django_db
User = get_user_model()
FCM = "https://fcm.googleapis.com/fcm/send/abc123"


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def make_keys():
    key = ec.generate_private_key(ec.SECP256R1())
    point = key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return {"p256dh": b64(point), "auth": b64(b"0123456789abcdef")}


@pytest.fixture(autouse=True)
def vapid_keys(settings):
    private, public = vapid.generate_keys()
    settings.VAPID_PRIVATE_KEY = private
    settings.VAPID_PUBLIC_KEY = public
    settings.VAPID_SUBJECT = "mailto:ops@example.test"
    vapid.reset_cache()
    yield
    vapid.reset_cache()


@pytest.fixture
def alice():
    return User.objects.create_user(username="alice", email="a@example.test", password="x")


@pytest.fixture
def bob():
    return User.objects.create_user(username="bob", email="b@example.test", password="x")


def client(user=None):
    api = APIClient()
    if user:
        api.force_authenticate(user)
    return api


def subscribe(user, endpoint=FCM, keys=None):
    return client(user).post(
        "/api/v1/push/subscriptions/",
        {"endpoint": endpoint, "keys": keys or make_keys()},
        format="json",
    )


@pytest.fixture
def sent(monkeypatch):
    """Capture what would reach the push service; `.outcome` can be set to an exception/status."""
    calls = SimpleNamespace(items=[], outcome=None)

    def fake(subscription_info, data=None, **kwargs):
        calls.items.append({"info": subscription_info, "data": data, **kwargs})
        if calls.outcome is not None:
            raise calls.outcome
        return SimpleNamespace(status_code=201)

    monkeypatch.setattr(sender, "webpush", fake)
    return calls


def gone(status):
    return WebPushException("push failed", response=SimpleNamespace(status_code=status))


# ── endpoint allowlist ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://fcm.googleapis.com/fcm/send/abc",
        "https://updates.push.services.mozilla.com/wpush/v2/abc",
        "https://updates.push.services.mozilla.com:443/wpush/v2/abc",
        "https://db5p.notify.windows.com/w/?token=abc",
        "https://web.push.apple.com/QGxx",
        "https://FCM.GOOGLEAPIS.COM/fcm/send/abc",
    ],
)
def test_known_push_services_are_accepted(endpoint):
    assert validate_endpoint(endpoint)


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://fcm.googleapis.com/fcm/send/abc",  # not https
        "https://evil.example.com/fcm.googleapis.com",
        "https://fcm.googleapis.com.evil.com/x",  # suffix trick
        "https://evilfcm.googleapis.com/x",  # dot boundary
        "https://fcm.googleapis.com@evil.com/x",  # userinfo trick
        "https://evil.com\\@fcm.googleapis.com/x",
        "https://evil.com#@fcm.googleapis.com/x",
        "https://user:pw@fcm.googleapis.com/x",
        "https://fcm.googleapis.com:8443/x",  # odd port
        "https://127.0.0.1/x",
        "https://169.254.169.254/latest/meta-data",
        "https://localhost/x",
        "https://[::1]/x",
        "https://fcm.googleapis.com",  # no path
        "https://fcm.googleapis.com/x#frag",
        "https://fcm.googleapis.com/x y",
        "https://fcm.googleapis.com/x\n",
        "https://fcm.googleapis.com/" + "a" * 600,
        "https://fcm.googIeapis.com/x",  # lookalike (capital I)
        "https://fcm.googleapis.com/x\x00",
        "file:///etc/passwd",
        "gopher://fcm.googleapis.com/x",
        "//fcm.googleapis.com/x",
        "",
    ],
)
def test_other_endpoints_are_rejected(endpoint):
    with pytest.raises(ValueError):
        validate_endpoint(endpoint)


def test_keys_must_be_real_p256_material():
    good = make_keys()
    assert validate_keys(good["p256dh"], good["auth"])
    for p256dh, auth in (
        ("", good["auth"]),
        (good["p256dh"], ""),
        ("not base64!!", good["auth"]),
        (b64(b"short"), good["auth"]),
        (good["p256dh"], b64(b"short")),
        (b64(b"\x05" + b"\x00" * 64), good["auth"]),  # wrong point prefix
    ):
        with pytest.raises(ValueError):
            validate_keys(p256dh, auth)


# ── subscription API ──────────────────────────────────────────────────────────


def test_config_exposes_only_the_public_key(alice, settings):
    data = client(alice).get("/api/v1/push/config/").data
    assert data == {"enabled": True, "public_key": settings.VAPID_PUBLIC_KEY}
    assert client().get("/api/v1/push/config/").status_code in (401, 403)


def test_feature_is_off_without_vapid_keys(alice, settings):
    settings.VAPID_PRIVATE_KEY = ""
    vapid.reset_cache()
    assert client(alice).get("/api/v1/push/config/").data == {"enabled": False, "public_key": ""}
    assert subscribe(alice).status_code == 503
    assert not PushSubscription.objects.exists()


def test_mismatched_public_key_disables_the_feature(alice, settings):
    settings.VAPID_PUBLIC_KEY = vapid.generate_keys()[1]
    vapid.reset_cache()
    assert client(alice).get("/api/v1/push/config/").data["enabled"] is False


def test_subscribe_stores_a_subscription(alice):
    keys = make_keys()
    resp = client(alice).post(
        "/api/v1/push/subscriptions/",
        {"endpoint": FCM, "keys": keys},
        format="json",
        HTTP_USER_AGENT="Firefox/1",
    )
    assert resp.status_code == 201
    sub = PushSubscription.objects.get(user=alice)
    assert (sub.endpoint, sub.p256dh, sub.auth, sub.user_agent) == (
        FCM,
        keys["p256dh"],
        keys["auth"],
        "Firefox/1",
    )
    assert not resp.content  # keys are never echoed back


def test_subscribe_requires_authentication():
    assert subscribe(None).status_code in (401, 403)


@pytest.mark.parametrize("endpoint", ["http://fcm.googleapis.com/x", "https://evil.example.com/x"])
def test_subscribe_rejects_bad_endpoints(alice, endpoint):
    assert subscribe(alice, endpoint=endpoint).status_code == 400
    assert not PushSubscription.objects.exists()


def test_subscribe_rejects_bad_keys(alice):
    resp = subscribe(alice, keys={"p256dh": "x", "auth": "y"})
    assert resp.status_code == 400 and not PushSubscription.objects.exists()


def test_at_most_ten_subscriptions_per_user(alice):
    for i in range(10):
        assert subscribe(alice, endpoint=f"{FCM}{i}").status_code == 201
    assert subscribe(alice, endpoint=f"{FCM}extra").status_code == 400
    # Re-registering one that already exists is not "another" subscription.
    assert subscribe(alice, endpoint=f"{FCM}3").status_code == 201
    assert PushSubscription.objects.filter(user=alice).count() == 10


def test_a_shared_browser_moves_the_subscription_to_the_new_user(alice, bob):
    subscribe(alice)
    assert subscribe(bob).status_code == 201
    assert PushSubscription.objects.get().user == bob


def test_unsubscribe_removes_only_your_own(alice, bob):
    subscribe(alice)
    api = client(bob)
    api.delete("/api/v1/push/subscriptions/", {"endpoint": FCM}, format="json")
    assert PushSubscription.objects.filter(user=alice).exists()
    client(alice).delete("/api/v1/push/subscriptions/", {"endpoint": FCM}, format="json")
    assert not PushSubscription.objects.exists()


def test_subscriptions_are_throttled_as_writes():
    from apps.push.views import SubscriptionView

    assert SubscriptionView.throttle_scope == "write"


# ── preferences ───────────────────────────────────────────────────────────────


def test_preferences_default_to_everything_on_and_can_be_changed(alice):
    api = client(alice)
    first = api.get("/api/v1/push/preferences/").data
    assert first["enabled"] is True and all(first["types"].values())
    resp = api.put(
        "/api/v1/push/preferences/",
        {"enabled": True, "types": {"messages": False}},
        format="json",
    )
    assert resp.status_code == 200 and resp.data["types"]["messages"] is False
    assert resp.data["types"]["replies"] is True
    assert (
        api.put("/api/v1/push/preferences/", {"types": {"bogus": True}}, format="json").status_code
        == 400
    )


# ── sending ───────────────────────────────────────────────────────────────────


def dm(alice, bob, text="my private text"):
    a, b = sorted((alice, bob), key=lambda u: u.id)
    conv = Conversation.objects.create(participant_a=a, participant_b=b)
    return Message.objects.create(conversation=conv, sender=alice, body=text)


def test_dm_push_is_generic_and_carries_no_message_text(
    alice, bob, sent, django_capture_on_commit_callbacks
):
    subscribe(bob)
    message = dm(alice, bob, "meet me at the secret place")
    with django_capture_on_commit_callbacks(execute=True):
        notify(bob, actor=alice, verb="dm", target=message)
    assert len(sent.items) == 1
    raw = sent.items[0]["data"]
    assert json.loads(raw) == {"type": "dm", "url": "/messages", "tag": "dm"}
    for leak in ("secret", "alice", "meet me"):
        assert leak not in raw
    assert sent.items[0]["vapid_claims"]["sub"] == "mailto:ops@example.test"
    assert sent.items[0]["info"]["endpoint"] == FCM


@pytest.mark.parametrize(
    ("verb", "url"),
    [
        ("reply", "/inbox"),
        ("comment", "/inbox"),
        ("mention", "/inbox"),
        ("follow", "/inbox"),
        ("modmail", "/modmail"),
        ("removal", "/inbox"),
        ("mod_action", "/inbox"),
        ("answer_accepted", "/inbox"),
        ("bounty_awarded", "/inbox"),
        ("bounty_refunded", "/inbox"),
    ],
)
def test_payload_url_is_a_fixed_same_origin_path(
    alice, bob, sent, verb, url, django_capture_on_commit_callbacks
):
    subscribe(bob)
    with django_capture_on_commit_callbacks(execute=True):
        notify(bob, actor=alice, verb=verb)
    payload = json.loads(sent.items[0]["data"])
    assert payload == {"type": verb, "url": url, "tag": verb}


def test_no_push_when_the_recipient_blocked_the_actor(
    alice, bob, sent, django_capture_on_commit_callbacks
):
    subscribe(bob)
    Block.objects.create(blocker=bob, blocked=alice)
    with django_capture_on_commit_callbacks(execute=True):
        assert notify(bob, actor=alice, verb="follow") is None
    assert sent.items == []


def test_no_push_when_the_community_is_muted(alice, bob, sent, django_capture_on_commit_callbacks):
    from apps.communities.models import Community, Membership

    community = Community.objects.create(slug="c", name="C", creator=alice)
    Membership.objects.create(user=bob, community=community, notify_level="off")
    subscribe(bob)
    with django_capture_on_commit_callbacks(execute=True):
        assert notify(bob, actor=alice, verb="comment", community=community) is None
    assert sent.items == []


def test_preferences_gate_sending(alice, bob, sent, django_capture_on_commit_callbacks):
    subscribe(bob)
    client(bob).put("/api/v1/push/preferences/", {"types": {"follows": False}}, format="json")
    with django_capture_on_commit_callbacks(execute=True):
        notify(bob, actor=alice, verb="follow")
    assert sent.items == []
    with django_capture_on_commit_callbacks(execute=True):
        notify(bob, actor=alice, verb="reply")
    assert len(sent.items) == 1
    client(bob).put("/api/v1/push/preferences/", {"enabled": False}, format="json")
    with django_capture_on_commit_callbacks(execute=True):
        notify(bob, actor=alice, verb="reply")
    assert len(sent.items) == 1


def test_expired_subscriptions_are_removed(alice, bob, sent, django_capture_on_commit_callbacks):
    for status in (404, 410):
        PushSubscription.objects.all().delete()
        subscribe(bob, endpoint=f"{FCM}{status}")
        sent.outcome = gone(status)
        with django_capture_on_commit_callbacks(execute=True):
            notify(bob, actor=alice, verb="follow")
        assert not PushSubscription.objects.exists()


def test_transient_failures_keep_the_subscription_but_are_counted_then_dropped(
    alice, bob, sent, django_capture_on_commit_callbacks
):
    subscribe(bob)
    sent.outcome = gone(500)
    for _ in range(sender.MAX_FAILURES - 1):
        with django_capture_on_commit_callbacks(execute=True):
            notify(bob, actor=alice, verb="follow")
    assert PushSubscription.objects.get().failures == sender.MAX_FAILURES - 1
    with django_capture_on_commit_callbacks(execute=True):
        notify(bob, actor=alice, verb="follow")
    assert not PushSubscription.objects.exists()


def test_success_resets_failures_and_stamps_last_used(
    alice, bob, sent, django_capture_on_commit_callbacks
):
    subscribe(bob)
    PushSubscription.objects.update(failures=3)
    with django_capture_on_commit_callbacks(execute=True):
        notify(bob, actor=alice, verb="follow")
    sub = PushSubscription.objects.get()
    assert sub.failures == 0 and sub.last_used is not None


def test_one_failing_endpoint_does_not_block_the_others(
    alice, bob, sent, django_capture_on_commit_callbacks
):
    subscribe(bob, endpoint=f"{FCM}a")
    subscribe(bob, endpoint=f"{FCM}b")
    sent.outcome = RuntimeError("network down")
    with django_capture_on_commit_callbacks(execute=True):
        notify(bob, actor=alice, verb="follow")
    assert len(sent.items) == 2


def test_endpoints_are_revalidated_at_send_time(
    alice, bob, sent, django_capture_on_commit_callbacks
):
    keys = make_keys()
    PushSubscription.objects.create(
        user=bob, endpoint="http://169.254.169.254/latest", p256dh=keys["p256dh"], auth=keys["auth"]
    )
    with django_capture_on_commit_callbacks(execute=True):
        notify(bob, actor=alice, verb="follow")
    assert sent.items == []
    assert not PushSubscription.objects.exists()


def test_nothing_is_sent_when_the_feature_is_off(
    alice, bob, sent, settings, django_capture_on_commit_callbacks
):
    subscribe(bob)
    settings.VAPID_PRIVATE_KEY = ""
    vapid.reset_cache()
    with django_capture_on_commit_callbacks(execute=True):
        notify(bob, actor=alice, verb="follow")
    assert sent.items == []


def test_inactive_recipients_get_nothing(alice, bob, sent, django_capture_on_commit_callbacks):
    subscribe(bob)
    User.objects.filter(pk=bob.pk).update(is_active=False)
    with django_capture_on_commit_callbacks(execute=True):
        notify(bob, actor=alice, verb="follow")
    assert sent.items == []


def test_the_real_request_is_vapid_signed_and_never_follows_redirects(
    alice, bob, monkeypatch, django_capture_on_commit_callbacks
):
    subscribe(bob)
    seen = {}

    def fake_post(self, url, **kwargs):
        seen.update(url=url, kwargs=kwargs, session=type(self))
        return SimpleNamespace(status_code=201, text="", headers={})

    import requests

    monkeypatch.setattr(requests.Session, "post", fake_post)
    with django_capture_on_commit_callbacks(execute=True):
        notify(bob, actor=alice, verb="follow")
    assert seen["url"] == FCM
    assert seen["kwargs"]["headers"]["authorization"].startswith("vapid ")
    assert seen["kwargs"]["timeout"] == sender.SEND_TIMEOUT
    assert seen["session"] is sender.NoRedirectSession

    # The session itself refuses redirects whatever the caller asks for.
    captured = {}

    def fake_request(self, method, url, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(requests.Session, "request", fake_request)
    sender.NoRedirectSession().request("POST", FCM, allow_redirects=True)
    assert captured["allow_redirects"] is False


# ── cleanup on session revocation ─────────────────────────────────────────────


def test_password_change_removes_every_subscription(alice):
    subscribe(alice)
    resp = client(alice).post(
        "/api/v1/users/me/password/",
        {"current_password": "x", "new_password": "BrandNewPass789!"},
        format="json",
    )
    assert resp.status_code == 200, resp.data
    assert not PushSubscription.objects.exists()


def test_account_deletion_removes_subscriptions_and_preferences(alice):
    from apps.users.services import delete_account

    subscribe(alice)
    PushPreference.objects.create(user=alice, enabled=False)
    delete_account(alice)
    assert not PushSubscription.objects.exists() and not PushPreference.objects.exists()


def test_mfa_changes_drop_subscriptions(alice):
    from apps.users import mfa

    subscribe(alice)
    mfa.revoke_all_sessions(alice)
    assert not PushSubscription.objects.exists()


# ── operator tooling ──────────────────────────────────────────────────────────


def test_generate_vapid_keys_prints_a_working_pair(settings):
    out = io.StringIO()
    call_command("generate_vapid_keys", stdout=out)
    lines = dict(line.split("=", 1) for line in out.getvalue().splitlines() if "=" in line)
    settings.VAPID_PRIVATE_KEY = lines["VAPID_PRIVATE_KEY"]
    settings.VAPID_PUBLIC_KEY = lines["VAPID_PUBLIC_KEY"]
    vapid.reset_cache()
    assert vapid.push_enabled() is True


# ── subscriptions follow their login session ─────────────────────────────────


def _session():
    """A real login: access token for the API, refresh cookie for logout."""
    api = APIClient()
    resp = api.post("/api/v1/auth/login/", {"username": "alice", "password": "x"}, format="json")
    assert resp.status_code == 200, resp.data
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")
    return api


def test_logout_removes_only_that_sessions_subscription(alice):
    first, second = _session(), _session()
    keys = make_keys()
    assert (
        first.post(
            "/api/v1/push/subscriptions/", {"endpoint": FCM + "1", "keys": keys}, format="json"
        ).status_code
        == 201
    )
    assert (
        second.post(
            "/api/v1/push/subscriptions/", {"endpoint": FCM + "2", "keys": keys}, format="json"
        ).status_code
        == 201
    )
    first.credentials()  # logout is cookie based
    assert first.post("/api/v1/auth/logout/").status_code == 204
    assert list(PushSubscription.objects.values_list("endpoint", flat=True)) == [FCM + "2"]


def test_the_session_id_survives_refresh_rotation(alice):
    api = _session()
    api.post("/api/v1/push/subscriptions/", {"endpoint": FCM, "keys": make_keys()}, format="json")
    assert api.post("/api/v1/auth/refresh/").status_code == 200  # rotates the refresh token
    api.credentials()
    api.post("/api/v1/auth/logout/")
    assert not PushSubscription.objects.exists()


def test_unbound_subscriptions_are_not_swept_by_a_logout(alice):
    # Subscriptions made without a session id (older tokens, tests) must never match "".
    PushSubscription.objects.create(
        user=alice, endpoint=FCM, p256dh=make_keys()["p256dh"], auth=make_keys()["auth"]
    )
    api = _session()
    api.credentials()
    api.post("/api/v1/auth/logout/")
    assert PushSubscription.objects.count() == 1


@pytest.mark.parametrize("verb", ["answer_accepted", "bounty_awarded", "bounty_refunded"])
def test_qa_pushes_follow_the_replies_switch(
    alice, bob, sent, verb, django_capture_on_commit_callbacks
):
    subscribe(bob)
    client(bob).put("/api/v1/push/preferences/", {"types": {"replies": False}}, format="json")
    with django_capture_on_commit_callbacks(execute=True):
        notify(bob, actor=alice, verb=verb)
    assert sent.items == []

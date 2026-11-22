import time

import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APIClient

from apps.realtime.tickets import aconsume_ticket, issue_ticket

User = get_user_model()
TICKET = reverse("api_v1:realtime:realtime-ticket")

consume = async_to_sync(aconsume_ticket)


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="alice", email="a@x.com", password="x")


@pytest.fixture
def api(alice):
    client = APIClient()
    client.force_authenticate(alice)
    return client


def test_ticket_requires_authentication(db):
    assert APIClient().post(TICKET).status_code == 401


def test_ticket_is_issued_uncached(api, alice, settings):
    response = api.post(TICKET)
    assert response.status_code == 201
    assert response["Cache-Control"] == "no-store"
    assert response.data["expires_in"] == settings.REALTIME_TICKET_TTL
    assert len(response.data["ticket"]) >= 40
    assert consume(response.data["ticket"]).user_id == alice.pk


def test_ticket_is_single_use(alice):
    ticket = issue_ticket(alice)
    assert consume(ticket).user_id == alice.pk
    assert consume(ticket) is None


def test_ticket_carries_the_password_fingerprint(alice):
    from rest_framework_simplejwt.utils import get_md5_hash_password

    claim = consume(issue_ticket(alice))
    # The socket compares it with the current password on redemption.
    assert claim.fingerprint == get_md5_hash_password(alice.password)


def test_ticket_is_stored_hashed(alice):
    ticket = issue_ticket(alice)
    # LocMemCache exposes its keys; the raw ticket must not be one of them (nor a value).
    assert not any(ticket in key for key in cache._cache)
    assert ticket not in [str(v) for v in cache._cache.values()]


def test_ticket_expires(alice, settings, monkeypatch):
    ticket = issue_ticket(alice)
    real_time = time.time
    monkeypatch.setattr(time, "time", lambda: real_time() + settings.REALTIME_TICKET_TTL + 1)
    assert consume(ticket) is None


@pytest.mark.parametrize("ticket", [None, "", 123, ["x"], "short", "x" * 500])
def test_garbage_tickets_are_rejected(ticket):
    assert consume(ticket) is None


def test_unknown_ticket_is_rejected(alice):
    issue_ticket(alice)
    assert consume("A" * 43) is None


def test_ticket_unavailable_when_realtime_is_off(api, settings):
    settings.CHANNEL_LAYERS = {}
    assert api.post(TICKET).status_code == 503


def test_ticket_endpoint_is_throttled(api, monkeypatch):
    from rest_framework.throttling import ScopedRateThrottle

    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"realtime_ticket": "2/min"})
    statuses = [api.post(TICKET).status_code for _ in range(3)]
    assert statuses == [201, 201, 429]


@pytest.mark.parametrize("stored", [7, {"user_id": 7}, {"user_id": 7, "extra": 1}])
def test_tickets_of_another_shape_are_rejected(stored):
    """A ticket left in the cache by an older release is refused, not misread."""
    from apps.realtime.tickets import _key

    cache.set(_key("B" * 43), stored)
    assert consume("B" * 43) is None


def test_ticket_carries_the_access_token_expiry(alice):
    from rest_framework_simplejwt.tokens import AccessToken

    token = AccessToken.for_user(alice)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    response = client.post(TICKET)
    assert response.status_code == 201
    # The socket may live no longer than the token that bought its ticket.
    assert consume(response.data["ticket"]).expires_at == token["exp"]

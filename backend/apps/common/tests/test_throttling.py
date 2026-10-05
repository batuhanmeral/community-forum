import pytest
from django.urls import reverse
from rest_framework.test import APIClient

REGISTER = reverse("api_v1:auth:auth-register")


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def tight_auth_throttle(monkeypatch):
    """Force the 'auth' scope rate down to 2/min for this test."""
    from rest_framework.throttling import ScopedRateThrottle

    monkeypatch.setattr(
        ScopedRateThrottle,
        "THROTTLE_RATES",
        {"auth": "2/min", "vote": "100/min", "write": "100/min"},
    )


@pytest.mark.django_db
def test_register_endpoint_throttled(api, tight_auth_throttle):
    payloads = [
        {"username": f"user{i}", "email": f"user{i}@x.com", "password": "StrongPass123!"}
        for i in range(4)
    ]
    statuses = [api.post(REGISTER, p, format="json").status_code for p in payloads]
    assert statuses[:2] == [201, 201]
    assert 429 in statuses[2:]


@pytest.mark.django_db
def test_register_with_default_rates_does_not_throttle_small_burst(api):
    """Sanity check: under the default 20/min auth rate, 3 registers succeed."""
    payloads = [
        {"username": f"vser{i}", "email": f"vser{i}@x.com", "password": "StrongPass123!"}
        for i in range(3)
    ]
    statuses = [api.post(REGISTER, p, format="json").status_code for p in payloads]
    assert statuses == [201, 201, 201]


def _register_payload(i: int) -> dict:
    return {"username": f"spoof{i}", "email": f"spoof{i}@x.com", "password": "StrongPass123!"}


@pytest.mark.django_db
def test_spoofed_forwarded_for_does_not_reset_throttle(api, tight_auth_throttle):
    statuses = [
        api.post(
            REGISTER, _register_payload(i), format="json", HTTP_X_FORWARDED_FOR=f"10.0.0.{i}"
        ).status_code
        for i in range(3)
    ]
    assert 429 in statuses


@pytest.mark.django_db
def test_behind_one_proxy_uses_the_proxy_appended_hop(api, tight_auth_throttle, settings):
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 1}
    statuses = [
        api.post(
            REGISTER,
            _register_payload(i),
            format="json",
            HTTP_X_FORWARDED_FOR=f"6.6.6.{i}, 203.0.113.7",
        ).status_code
        for i in range(3)
    ]
    assert 429 in statuses

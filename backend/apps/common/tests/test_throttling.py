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
        {"username": f"u{i}", "email": f"u{i}@x.com", "password": "StrongPass123!"}
        for i in range(4)
    ]
    statuses = [api.post(REGISTER, p, format="json").status_code for p in payloads]
    assert statuses[:2] == [201, 201]
    assert 429 in statuses[2:]


@pytest.mark.django_db
def test_register_with_default_rates_does_not_throttle_small_burst(api):
    """Sanity check: under the default 20/min auth rate, 3 registers succeed."""
    payloads = [
        {"username": f"v{i}", "email": f"v{i}@x.com", "password": "StrongPass123!"}
        for i in range(3)
    ]
    statuses = [api.post(REGISTER, p, format="json").status_code for p in payloads]
    assert statuses == [201, 201, 201]

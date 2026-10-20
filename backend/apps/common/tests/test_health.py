from unittest.mock import patch

import pytest
from django.db import OperationalError, connection
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

HEALTH = reverse("api_v1:common:health")


@pytest.fixture
def client():
    return APIClient()


def test_health_ok_for_anonymous(client):
    resp = client.get(HEALTH)
    assert resp.status_code == 200 and resp.json() == {"status": "ok"}


def test_health_ignores_a_bad_bearer_token(client):
    resp = client.get(HEALTH, HTTP_AUTHORIZATION="Bearer garbage")
    assert resp.status_code == 200


def test_health_is_not_throttled(client):
    # Anon rate is 60/min; the probe must stay reachable beyond it.
    codes = {client.get(HEALTH).status_code for _ in range(70)}
    assert codes == {200}


def test_health_reports_db_outage_without_details(client):
    with patch(
        "apps.common.views.connection.ensure_connection",
        side_effect=OperationalError("secret-host"),
    ):
        resp = client.get(HEALTH)
    assert resp.status_code == 503 and resp.json() == {"status": "unavailable"}
    assert b"secret-host" not in resp.content


def test_health_is_exempt_from_ssl_redirect():
    # SecurityMiddleware reads the settings at init, so build the client inside the override.
    with override_settings(SECURE_SSL_REDIRECT=True):
        assert APIClient().get(HEALTH).status_code == 200
        assert APIClient().get(reverse("api_v1:communities:community-list")).status_code == 301


def test_health_pings_an_already_open_connection(client):
    connection.ensure_connection()
    with patch("apps.common.views.connection.cursor", side_effect=OperationalError("gone")):
        resp = client.get(HEALTH)
    assert resp.status_code == 503 and resp.json() == {"status": "unavailable"}

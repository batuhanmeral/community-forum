import json
import secrets

import pytest
from asgiref.sync import async_to_sync

from apps.realtime.tests.communicator import WebsocketClient, http_get
from config.realtime import channel_layers, websocket_origins
from config.tests.test_prod_settings import _run_prod


def test_channel_layers_disabled_without_redis():
    assert channel_layers("", db=2) == {}


def test_channel_layers_use_their_own_redis_db():
    layers = channel_layers("redis://redis:6379/1", db=2)
    assert layers["default"]["BACKEND"] == "channels_redis.core.RedisChannelLayer"
    config = layers["default"]["CONFIG"]
    assert config["hosts"][0]["address"] == "redis://redis:6379/2"
    assert config["prefix"]


def test_channel_layer_reads_outlast_its_blocking_pop():
    # redis-py 8 defaults to a 5 s socket timeout, the same as channels-redis's blocking
    # BZPOPMIN: an idle consumer's read would time out and crash the socket.
    from channels_redis.core import RedisChannelLayer

    host = channel_layers("redis://redis:6379/1", db=2)["default"]["CONFIG"]["hosts"][0]
    assert host["socket_timeout"] > RedisChannelLayer.brpop_timeout


def test_channel_layers_keep_scheme_credentials_and_options():
    layers = channel_layers("rediss://:pw@cache.internal:6380/0?ssl_cert_reqs=required", db=3)
    host = layers["default"]["CONFIG"]["hosts"][0]
    assert host["address"] == "rediss://:pw@cache.internal:6380/3?ssl_cert_reqs=required"


def test_websocket_origins_are_frontend_origin_plus_trusted_origins():
    origins = websocket_origins(
        "https://forum.example.com/some/path", ["https://forum.example.com", "https://alt.example"]
    )
    assert origins == ["https://forum.example.com", "https://alt.example"]


def test_websocket_origins_skip_blank_entries():
    assert websocket_origins("http://localhost:5173", ["", " "]) == ["http://localhost:5173"]


_REALTIME_CODE = (
    "import django, json; django.setup(); from django.conf import settings as s; "
    "print(json.dumps({'layers': s.CHANNEL_LAYERS, 'origins': s.REALTIME_ALLOWED_ORIGINS}))"
)


def test_prod_enables_realtime_when_redis_is_configured():
    result = _run_prod(
        _REALTIME_CODE,
        SECRET_KEY=secrets.token_urlsafe(50),
        REDIS_URL="redis://redis:6379/1",
        FRONTEND_URL="https://forum.example.com",
        CSRF_TRUSTED_ORIGINS="https://forum.example.com,https://www.forum.example.com",
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["layers"]["default"]["CONFIG"]["hosts"][0]["address"] == "redis://redis:6379/2"
    assert data["origins"] == ["https://forum.example.com", "https://www.forum.example.com"]


def test_prod_disables_realtime_without_redis():
    result = _run_prod(_REALTIME_CODE, SECRET_KEY=secrets.token_urlsafe(50), REDIS_URL="")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["layers"] == {}


@pytest.mark.django_db(transaction=True)
def test_asgi_app_still_serves_django_http():
    from config.asgi import application

    assert async_to_sync(http_get)(application, "/api/v1/health/") == 200


# Channels consumers close stale DB connections on connect, so DB access must be allowed.
@pytest.mark.django_db(transaction=True)
def test_asgi_app_rejects_unknown_websocket_origin():
    from config.asgi import application

    async def probe():
        client = WebsocketClient(application, "/ws/v1/stream/", origin="https://evil.example")
        return await client.connect()

    assert async_to_sync(probe)()[0] is False


# Channels consumers close stale DB connections on connect, so DB access must be allowed.
@pytest.mark.django_db(transaction=True)
def test_asgi_app_rejects_websocket_without_origin():
    from config.asgi import application

    async def probe():
        return await WebsocketClient(application, "/ws/v1/stream/", origin=None).connect()

    assert async_to_sync(probe)()[0] is False

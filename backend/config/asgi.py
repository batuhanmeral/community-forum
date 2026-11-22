"""
ASGI entry point of the realtime service (uvicorn): Django HTTP plus the WebSocket event stream.

The API itself keeps running under gunicorn/WSGI (config/wsgi.py).
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

# Set up Django before importing anything that touches models.
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import OriginValidator  # noqa: E402
from django.conf import settings  # noqa: E402

from apps.realtime.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        # Browsers always send Origin on a WebSocket handshake; a missing or foreign one is refused.
        "websocket": OriginValidator(
            URLRouter(websocket_urlpatterns), settings.REALTIME_ALLOWED_ORIGINS
        ),
    }
)

"""ASGI test clients.

channels.testing's package __init__ imports Daphne (live-server tests), which this project does not
ship; these are the same thin wrappers over asgiref's ApplicationCommunicator.
"""

import json

from asgiref.testing import ApplicationCommunicator


class WebsocketClient(ApplicationCommunicator):
    def __init__(self, application, path, *, origin: str | None = "http://localhost:5173"):
        headers = [(b"origin", origin.encode())] if origin else []
        super().__init__(
            application,
            {
                "type": "websocket",
                "path": path,
                "query_string": b"",
                "headers": headers,
                "subprotocols": [],
            },
        )

    async def connect(self, timeout: float = 1):
        """(True, None) when accepted, (False, close code) when refused."""
        await self.send_input({"type": "websocket.connect"})
        response = await self.receive_output(timeout)
        if response["type"] == "websocket.close":
            return False, response.get("code", 1000)
        return True, None

    async def send_json(self, data) -> None:
        await self.send_input({"type": "websocket.receive", "text": json.dumps(data)})

    async def send_text(self, text: str) -> None:
        await self.send_input({"type": "websocket.receive", "text": text})

    async def receive_json(self, timeout: float = 1):
        response = await self.receive_output(timeout)
        assert response["type"] == "websocket.send", response
        return json.loads(response["text"])

    async def receive_close(self, timeout: float = 1) -> int:
        response = await self.receive_output(timeout)
        assert response["type"] == "websocket.close", response
        return response.get("code", 1000)

    async def disconnect(self, code: int = 1000) -> None:
        await self.send_input({"type": "websocket.disconnect", "code": code})
        await self.wait(timeout=1)


async def http_get(application, path: str) -> int:
    communicator = ApplicationCommunicator(
        application,
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [(b"host", b"localhost")],
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 1234),
        },
    )
    await communicator.send_input({"type": "http.request", "body": b""})
    start = await communicator.receive_output(5)
    await communicator.wait(timeout=5)
    return start["status"]

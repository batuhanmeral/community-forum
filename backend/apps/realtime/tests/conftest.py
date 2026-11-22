import pytest
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


@pytest.fixture(autouse=True)
def _fresh_admission():
    """The pending-socket counter is process-global; a test that leaks one must not starve others."""
    from apps.realtime import admission

    yield
    admission._pending = 0
    admission._memory.clear()


@pytest.fixture(autouse=True)
def _fresh_channel_layer():
    """The in-memory layer is process-global; groups must not leak between tests."""
    yield
    layer = get_channel_layer()
    if layer is not None:
        async_to_sync(layer.flush)()

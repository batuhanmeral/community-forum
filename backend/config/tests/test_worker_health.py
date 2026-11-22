import os
import subprocess
import sys


def probe(ready):
    return subprocess.run(
        [sys.executable, "-m", "config.worker_health"],
        env={**os.environ, "WORKER_READY_FILE": str(ready)},
        capture_output=True,
        timeout=10,
    ).returncode


def test_readiness_requires_marker_and_live_worker(tmp_path):
    ready = tmp_path / "worker.ready"
    assert probe(ready) != 0
    worker = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        ready.write_text(str(worker.pid))
        assert probe(ready) == 0
    finally:
        worker.terminate()
        worker.wait(timeout=10)
    assert probe(ready) != 0


def test_readiness_rejects_malformed_marker(tmp_path):
    ready = tmp_path / "worker.ready"
    for content in ["", "invalid", "0", "-1"]:
        ready.write_text(content)
        assert probe(ready) != 0

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "worker-entrypoint.sh"


def test_worker_runs_maintenance_at_startup_and_periodically(tmp_path):
    python = tmp_path / "python"
    python.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$CALL_LOG"\n')
    python.chmod(0o755)
    sleep = tmp_path / "sleep"
    sleep.write_text(
        '#!/bin/sh\nif [ -f "$SLEEP_MARKER" ]; then exit 1; fi\ntouch "$SLEEP_MARKER"\n'
    )
    sleep.chmod(0o755)
    log = tmp_path / "calls"
    result = subprocess.run(
        ["sh", str(SCRIPT), "python", "manage.py", "db_worker", "--no-reload"],
        env={
            **os.environ,
            "PATH": f"{tmp_path}:{os.environ['PATH']}",
            "CALL_LOG": str(log),
            "SLEEP_MARKER": str(tmp_path / "slept"),
        },
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    calls = log.read_text().splitlines()
    assert calls[:3] == [
        "manage.py recover_stale_tasks",
        "manage.py prune_db_task_results --min-age-days 14 --failed-min-age-days 30",
        "manage.py expire_bounties",
    ]
    assert calls.count("manage.py expire_bounties") == 2
    assert calls.count("manage.py recover_stale_tasks") == 2
    assert (
        calls.count("manage.py prune_db_task_results --min-age-days 14 --failed-min-age-days 30")
        == 2
    )
    assert calls.count("manage.py db_worker --no-reload") == 1


@pytest.mark.parametrize("phase", ["startup", "periodic"])
@pytest.mark.parametrize(
    "command", ["recover_stale_tasks", "prune_db_task_results", "expire_bounties"]
)
def test_maintenance_failure_is_logged_and_worker_keeps_running(tmp_path, phase, command):
    python = tmp_path / "python"
    python.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$*" >> "$CALL_LOG"\n'
        'phase=startup\n[ ! -f "$SLEEP_MARKER" ] || phase=periodic\n'
        'if [ "$2" = "$FAIL_COMMAND" ] && [ "$phase" = "$FAIL_PHASE" ]; then exit 1; fi\n'
    )
    python.chmod(0o755)
    sleep = tmp_path / "sleep"
    sleep.write_text(
        '#!/bin/sh\nif [ -f "$SLEEP_MARKER" ]; then exit 1; fi\ntouch "$SLEEP_MARKER"\n'
    )
    sleep.chmod(0o755)
    log = tmp_path / "calls"
    result = subprocess.run(
        ["sh", str(SCRIPT), "python", "manage.py", "db_worker", "--no-reload"],
        env={
            **os.environ,
            "PATH": f"{tmp_path}:{os.environ['PATH']}",
            "CALL_LOG": str(log),
            "SLEEP_MARKER": str(tmp_path / "slept"),
            "FAIL_PHASE": phase,
            "FAIL_COMMAND": command,
        },
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    calls = log.read_text().splitlines()
    assert calls.count("manage.py db_worker --no-reload") == 1
    assert calls.count("manage.py recover_stale_tasks") == 2
    assert "Task maintenance failed" in result.stderr


def test_restart_clears_old_readiness_before_maintenance(tmp_path):
    ready = tmp_path / "worker.ready"
    ready.write_text(str(os.getpid()))
    python = tmp_path / "python"
    python.write_text('#!/bin/sh\n[ ! -e "$WORKER_READY_FILE" ]\n')
    python.chmod(0o755)
    sleep = tmp_path / "sleep"
    sleep.write_text("#!/bin/sh\nexit 1\n")
    sleep.chmod(0o755)
    result = subprocess.run(
        ["sh", str(SCRIPT), "python", "manage.py", "db_worker"],
        env={
            **os.environ,
            "PATH": f"{tmp_path}:{os.environ['PATH']}",
            "WORKER_READY_FILE": str(ready),
        },
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert not ready.exists()


def test_worker_exit_failure_is_not_hidden(tmp_path):
    python = tmp_path / "python"
    python.write_text("#!/bin/sh\nexit 0\n")
    python.chmod(0o755)
    sleep = tmp_path / "sleep"
    sleep.write_text("#!/bin/sh\nexit 1\n")
    sleep.chmod(0o755)
    result = subprocess.run(
        ["sh", str(SCRIPT), "sh", "-c", "exit 7"],
        env={**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}"},
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 7

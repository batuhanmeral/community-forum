"""Probe startup readiness and worker process liveness without booting Django."""

import os
from pathlib import Path


def main():
    try:
        pid = int(Path(os.environ["WORKER_READY_FILE"]).read_text())
        if pid <= 0:
            return 1
        os.kill(pid, 0)
    except (KeyError, OSError, ValueError):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env sh
set -eu

# A container restart can retain a marker left by SIGKILL.
if [ -n "${WORKER_READY_FILE:-}" ]; then
    rm -f "$WORKER_READY_FILE"
fi

maintenance() {
    python manage.py recover_stale_tasks &&
}

# Migrations belong to the API container, which is healthy before we start.
maintenance || echo "Task maintenance failed at startup; will retry in one hour." >&2
(
    while sleep 3600; do
        maintenance || echo "Task maintenance failed; will retry in one hour." >&2
    done
) &

# db_worker stays PID 1 and receives SIGTERM directly. The container runtime
# stops the maintenance child when the worker exits.
exec "$@"

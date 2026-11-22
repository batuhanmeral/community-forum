"""Project safeguards around the pinned django-tasks-db worker."""

import os
from pathlib import Path

from django.core.management.base import CommandError
from django.db import transaction
from django.tasks.base import TaskResultStatus
from django.utils.autoreload import DJANGO_AUTORELOAD_ENV, run_with_reloader
from django_tasks_db.management.commands import db_worker
from django_tasks_db.models import DBTaskResult


class FinishingTaskResult:
    """Keep recovery authoritative while retaining upstream completion/signals."""

    def __init__(self, result):
        self.result = result

    def __getattr__(self, name):
        return getattr(self.result, name)

    def _finish(self, method, value):
        # Recovery's conditional UPDATE and this short row lock serialize the
        # final transition. Never hold the lock while executing a task/SMTP.
        using = self.result._state.db
        with transaction.atomic(using=using):
            self.result = (
                DBTaskResult.objects.using(using).select_for_update().get(pk=self.result.pk)
            )
            if self.result.status == TaskResultStatus.RUNNING:
                getattr(self.result, method)(value)

    def set_successful(self, value):
        self._finish("set_successful", value)

    def set_failed(self, exc):
        self._finish("set_failed", exc)


class Worker(db_worker.Worker):
    def run_task(self, db_task_result):
        super().run_task(FinishingTaskResult(db_task_result))

    def run(self):
        ready_file = os.environ.get("WORKER_READY_FILE")
        if not ready_file:
            return super().run()
        ready = Path(ready_file)
        ready.unlink(missing_ok=True)
        try:
            # Prove database access before declaring this loop ready. A PID in
            # the marker lets the healthcheck reject a dead worker as well.
            DBTaskResult.objects.filter(backend_name=self.backend_name).exists()
            ready.write_text(str(os.getpid()))
            return super().run()
        finally:
            ready.unlink(missing_ok=True)


class Command(db_worker.Command):
    # Upstream has no worker factory hook. Reuse its parser/logging and keep
    # this wiring aligned with django-tasks-db's pinned Command.handle.
    def handle(self, *, verbosity, queue_name, exclude_queues, reload, **options):
        self.configure_logging(verbosity)
        if reload and options["batch"]:
            db_worker.logger.warning("--reload is disabled in batch mode.")
            reload = False
        excluded = exclude_queues.split(",") if exclude_queues else []
        queues = queue_name.split(",")
        if excluded and "*" not in queues:
            raise CommandError("--exclude-queues can only be used with --queue-name=*")
        worker = Worker(
            queue_names=queues,
            excluded_queue_names=excluded,
            **{
                key: options[key]
                for key in (
                    "interval",
                    "batch",
                    "backend_name",
                    "startup_delay",
                    "max_tasks",
                    "worker_id",
                )
            },
        )
        if reload:
            if os.environ.get(DJANGO_AUTORELOAD_ENV) == "true":
                worker.configure_signals()
            run_with_reloader(worker.run)
        else:
            worker.configure_signals()
            worker.run()

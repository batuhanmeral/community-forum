from uuid import UUID

import pytest
from django.tasks import default_task_backend, task
from django.tasks.base import TaskResultStatus
from django.test import override_settings

from config.settings.base import TASKS


@task()
def add_numbers(left, right):
    return left + right


@pytest.mark.django_db(transaction=True)
@override_settings(TASKS=TASKS)
def test_configured_queue_persists_and_worker_completes_task(
    task_command,
):
    result = add_numbers.enqueue(2, 3)
    saved = default_task_backend.get_result(result.id)
    assert saved.status == TaskResultStatus.READY
    task_command("db_worker", batch=True, verbosity=0)
    saved.refresh()
    assert saved.status == TaskResultStatus.SUCCESSFUL
    assert saved.return_value == 5


@pytest.mark.django_db(transaction=True)
@override_settings(TASKS=TASKS)
def test_retention_prunes_only_old_finished_tasks(
    task_command,
):
    from datetime import timedelta

    from django.utils import timezone
    from django_tasks_db.models import DBTaskResult

    now = timezone.now()
    old_success, recent_success, old_failure, retained_failure, pending = [
        add_numbers.enqueue(2, 3).id for _ in range(5)
    ]
    for result_id, status, age in [
        (old_success, TaskResultStatus.SUCCESSFUL, 15),
        (recent_success, TaskResultStatus.SUCCESSFUL, 1),
        (old_failure, TaskResultStatus.FAILED, 31),
        (retained_failure, TaskResultStatus.FAILED, 15),
    ]:
        DBTaskResult.objects.filter(pk=result_id).update(
            status=status, finished_at=now - timedelta(days=age)
        )
    DBTaskResult.objects.filter(pk=pending).update(enqueued_at=now - timedelta(days=60))
    task_command("prune_db_task_results", min_age_days=14, failed_min_age_days=30, verbosity=0)
    assert set(DBTaskResult.objects.values_list("id", flat=True)) == {
        UUID(result_id) for result_id in [recent_success, retained_failure, pending]
    }


@pytest.mark.django_db(transaction=True)
@override_settings(TASKS=TASKS)
def test_recovery_fails_only_stale_running_jobs(
    task_command,
):
    from datetime import timedelta

    from django.utils import timezone
    from django_tasks_db.models import DBTaskResult

    now = timezone.now()
    stale, recent, pending, finished, other_backend = [
        add_numbers.enqueue(2, 3).id for _ in range(5)
    ]
    for result_id, status, age in [
        (stale, TaskResultStatus.RUNNING, 61),
        (recent, TaskResultStatus.RUNNING, 59),
        (pending, TaskResultStatus.READY, 120),
        (finished, TaskResultStatus.SUCCESSFUL, 120),
        (other_backend, TaskResultStatus.RUNNING, 120),
    ]:
        DBTaskResult.objects.filter(pk=result_id).update(
            status=status, started_at=now - timedelta(minutes=age)
        )
    DBTaskResult.objects.filter(pk=other_backend).update(backend_name="other")
    task_command("recover_stale_tasks", older_than_minutes=60)
    recovered = DBTaskResult.objects.get(pk=stale)
    assert recovered.status == TaskResultStatus.FAILED
    assert recovered.finished_at is not None
    assert recovered.task_result.errors[0].exception_class is RuntimeError
    assert "interrupted" in recovered.traceback.lower()
    assert DBTaskResult.objects.get(pk=recent).status == TaskResultStatus.RUNNING
    assert DBTaskResult.objects.get(pk=pending).status == TaskResultStatus.READY
    assert DBTaskResult.objects.get(pk=finished).status == TaskResultStatus.SUCCESSFUL
    assert DBTaskResult.objects.get(pk=other_backend).status == TaskResultStatus.RUNNING


@pytest.mark.django_db
@pytest.mark.parametrize("minutes", [0, -1])
def test_recovery_rejects_nonpositive_age(task_command, minutes):
    from django.core.management.base import CommandError

    with pytest.raises(CommandError, match="positive"):
        task_command("recover_stale_tasks", older_than_minutes=minutes)


@pytest.mark.django_db(transaction=True)
@override_settings(TASKS=TASKS)
def test_worker_command_restores_process_state_and_avoids_random_delay(task_command, monkeypatch):
    import logging
    import signal

    from django_tasks_db.management.commands import db_worker

    signals = [signal.SIGINT, signal.SIGTERM, signal.SIGQUIT]
    handlers = {sig: signal.getsignal(sig) for sig in signals}
    loggers = [logging.getLogger(name) for name in ["django.tasks", "django_tasks_db"]]
    levels = [logger.level for logger in loggers]
    sleeps = []
    monkeypatch.setattr(db_worker.time, "sleep", sleeps.append)
    try:
        task_command("db_worker", batch=True, verbosity=0)
        assert {sig: signal.getsignal(sig) for sig in signals} == handlers
        assert [logger.level for logger in loggers] == levels
        assert sleeps == []
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
        for logger, level in zip(loggers, levels, strict=True):
            logger.setLevel(level)


@task()
def finish_after_recovery(fail):
    from datetime import timedelta

    from django.core.management import call_command
    from django.utils import timezone
    from django_tasks_db.models import DBTaskResult

    DBTaskResult.objects.filter(status=TaskResultStatus.RUNNING).update(
        started_at=timezone.now() - timedelta(minutes=61)
    )
    call_command("recover_stale_tasks", verbosity=0)
    if fail:
        raise ValueError("late task failure")
    return "late success"


@pytest.mark.django_db(transaction=True)
@override_settings(TASKS=TASKS)
@pytest.mark.parametrize("fail", [False, True])
def test_late_task_completion_preserves_recovery_result(task_command, fail):
    from django.tasks.signals import task_finished
    from django_tasks_db.models import DBTaskResult

    finished = []

    def record(sender, task_result, **kwargs):
        finished.append(task_result.status)

    result = finish_after_recovery.enqueue(fail)
    task_finished.connect(record, weak=False)
    try:
        task_command("db_worker")
    finally:
        task_finished.disconnect(record)
    saved = DBTaskResult.objects.get(pk=result.id)
    assert saved.status == TaskResultStatus.FAILED
    assert saved.return_value is None
    assert saved.exception_class_path == "builtins.RuntimeError"
    assert "interrupted" in saved.traceback.lower()
    assert finished == [TaskResultStatus.FAILED]


@pytest.mark.django_db(transaction=True)
@override_settings(TASKS=TASKS)
@pytest.mark.parametrize("crash", [False, True])
def test_worker_readiness_is_removed_on_exit(task_command, monkeypatch, tmp_path, crash):
    import os

    from django_tasks_db.management.commands.db_worker import Worker

    ready = tmp_path / "worker.ready"
    ready.write_text("stale previous process")
    monkeypatch.setenv("WORKER_READY_FILE", str(ready))

    def run(self):
        assert ready.read_text() == str(os.getpid())
        if crash:
            raise RuntimeError("worker loop died")

    monkeypatch.setattr(Worker, "run", run)
    if crash:
        with pytest.raises(RuntimeError, match="worker loop died"):
            task_command("db_worker")
    else:
        task_command("db_worker")
    assert not ready.exists()

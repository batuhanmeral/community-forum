from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.tasks.base import TaskResultStatus
from django.utils import timezone
from django_tasks_db.models import DBTaskResult


class Command(BaseCommand):
    help = "Fail interrupted default-backend tasks running longer than the age limit."

    def add_arguments(self, parser):
        parser.add_argument("--older-than-minutes", type=int, default=60)

    def handle(self, *, older_than_minutes, **options):
        if older_than_minutes <= 0:
            raise CommandError("Age must be a positive number of minutes.")
        now = timezone.now()
        # One conditional UPDATE is atomic with concurrent worker completions.
        # Never retry automatically: a killed job may already have delivered mail.
        recovered = DBTaskResult.objects.filter(
            backend_name="default",
            status=TaskResultStatus.RUNNING,
            started_at__lt=now - timedelta(minutes=older_than_minutes),
        ).update(
            status=TaskResultStatus.FAILED,
            finished_at=now,
            exception_class_path="builtins.RuntimeError",
            traceback="Worker interrupted or task exceeded the running age limit; not retried.",
        )
        self.stdout.write(f"Marked {recovered} stale running task(s) as failed.")

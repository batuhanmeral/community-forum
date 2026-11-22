import os

from botocore.exceptions import BotoCoreError, ClientError
from django.apps import apps
from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.storage import FileSystemStorage, default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db import models


class Command(BaseCommand):
    help = (
        "Copy every media file referenced by the database from MEDIA_ROOT to the configured "
        "(S3) default storage under the same key, so no row needs rewriting. Safe to re-run; "
        "existing objects are verified by size and never overwritten."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="List what would be copied.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        destination = default_storage
        if isinstance(destination, FileSystemStorage) and str(destination.location) == str(
            settings.MEDIA_ROOT
        ):
            raise CommandError(
                "The default storage is the local MEDIA_ROOT; set STORAGE_BACKEND=s3 first."
            )
        source = FileSystemStorage(location=str(settings.MEDIA_ROOT))

        copied = skipped = problems = 0
        for name in self._referenced_names():
            try:
                # FileSystemStorage.path() refuses anything that escapes MEDIA_ROOT.
                local_path = source.path(name)
                # Never follow a symlink out of MEDIA_ROOT (a planted link could expose any file).
                if os.path.realpath(local_path) != os.path.abspath(local_path):
                    raise SuspiciousFileOperation(name)
                if not source.exists(name):
                    raise FileNotFoundError(name)
                local_size = source.size(name)
                if destination.exists(name):
                    if destination.size(name) == local_size:
                        skipped += 1
                    else:
                        problems += 1
                        self.stderr.write(f"MISMATCH {name}: remote size differs; left untouched")
                    continue
                if dry_run:
                    copied += 1
                    self.stdout.write(f"would copy {name}")
                    continue
                with source.open(name) as handle:
                    saved = destination.save(name, handle)
                if saved != name or destination.size(name) != local_size:
                    problems += 1
                    self.stderr.write(f"VERIFY FAILED {name}: stored as {saved!r}")
                    continue
                copied += 1
            except SuspiciousFileOperation:
                problems += 1
                self.stderr.write(f"REFUSED {name!r}: path escapes MEDIA_ROOT or is a symlink")
            except (BotoCoreError, ClientError) as exc:
                # One failing object must not abort a long migration; the summary lists it.
                problems += 1
                self.stderr.write(f"STORAGE ERROR {name}: {type(exc).__name__}")
            except (OSError, FileNotFoundError) as exc:
                problems += 1
                self.stderr.write(f"MISSING {name}: {exc}")

        verb = "would copy" if dry_run else "copied"
        self.stdout.write(f"{verb} {copied}, already there {skipped}, problems {problems}")
        if problems:
            raise CommandError(f"{problems} problem(s); see messages above.")

    def _referenced_names(self):
        seen = set()
        for model in apps.get_models():
            for field in model._meta.get_fields():
                if not isinstance(field, models.FileField):
                    continue
                rows = (
                    model._default_manager.exclude(**{field.name: ""})
                    .exclude(**{f"{field.name}__isnull": True})
                    .values_list(field.name, flat=True)
                )
                for name in rows.iterator():
                    if name and name not in seen:
                        seen.add(name)
                        yield name

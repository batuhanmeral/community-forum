from django.core.management.base import BaseCommand

from apps.push.vapid import generate_keys


class Command(BaseCommand):
    help = "Print a fresh VAPID key pair for the environment (nothing is stored or logged)."

    def handle(self, *args, **options):
        private, public = generate_keys()
        self.stdout.write(f"VAPID_PRIVATE_KEY={private}")
        self.stdout.write(f"VAPID_PUBLIC_KEY={public}")
        self.stdout.write(
            "VAPID_SUBJECT=mailto:you@example.com  # a contact push services can reach"
        )

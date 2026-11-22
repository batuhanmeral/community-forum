from django.core.management.base import BaseCommand

from apps.posts import qa


class Command(BaseCommand):
    help = "Refund open bounties that expired or whose question was removed (idempotent)."

    def handle(self, *args, **options):
        self.stdout.write(f"Refunded {qa.expire_bounties()} bounties.")

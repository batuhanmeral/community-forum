from django.core.management.base import BaseCommand

from apps.users import mfa
from apps.users.models import MfaDevice


class Command(BaseCommand):
    help = (
        "Re-encrypt every stored TOTP secret under the first key of MFA_ENCRYPTION_KEY. Put the "
        "new key first and keep the old one listed, run this, then drop the old key."
    )

    def handle(self, *args, **options):
        rotated = 0
        for device in MfaDevice.objects.all():
            device.secret_encrypted = mfa.reencrypt_secret(device.secret_encrypted)
            device.save(update_fields=["secret_encrypted"])
            rotated += 1
        if options["verbosity"]:
            self.stdout.write(f"Re-encrypted {rotated} secret(s).")

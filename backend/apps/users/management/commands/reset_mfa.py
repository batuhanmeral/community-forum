import logging

from django.core.management.base import BaseCommand, CommandError

from apps.users import mfa
from apps.users.models import MfaChallenge, MfaDevice, MfaFailure, MfaRecoveryCode, User

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Remove two-factor authentication (device, recovery codes, pending challenges, failure "
        "history) and end every session, for users who lost both their device and recovery codes. "
        "Verify the person's identity out of band first."
    )

    def add_arguments(self, parser):
        parser.add_argument("--user", help="Username to reset.")
        parser.add_argument("--all", action="store_true", help="Reset every user.")
        parser.add_argument("--yes", action="store_true", help="Required together with --all.")

    def handle(self, *args, **options):
        if bool(options["user"]) == bool(options["all"]):
            raise CommandError("Give exactly one of --user NAME or --all.")
        if options["all"]:
            if not options["yes"]:
                raise CommandError("--all removes 2FA for everyone; repeat with --yes to confirm.")
            users = User.objects.filter(mfa_device__isnull=False).distinct()
        else:
            user = User.objects.filter(username=options["user"]).first()
            if user is None:
                raise CommandError(f"No user named {options['user']!r}.")
            users = [user]
        count = 0
        for user in users:
            for model in (MfaDevice, MfaRecoveryCode, MfaChallenge, MfaFailure):
                model.objects.filter(user=user).delete()
            mfa.revoke_all_sessions(user)
            logger.warning("MFA reset for user %s via management command", user.pk)
            count += 1
        self.stdout.write(f"Reset two-factor authentication for {count} user(s).")

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Community, Membership


@receiver(post_save, sender=Community)
def create_creator_membership(sender, instance, created, **kwargs):
    if created:
        Membership.objects.get_or_create(
            user=instance.creator,
            community=instance,
            defaults={"role": Membership.Role.ADMIN},
        )

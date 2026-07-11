from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum

from apps.comments.models import Comment
from apps.posts.models import Post
from apps.votes.models import Vote

User = get_user_model()


class Command(BaseCommand):
    help = "Recompute User.post_karma and comment_karma from Vote rows."

    @transaction.atomic
    def handle(self, *args, **opts):
        post_ct = ContentType.objects.get_for_model(Post)
        comment_ct = ContentType.objects.get_for_model(Comment)

        post_totals = self._totals_by_author(Post, post_ct)
        comment_totals = self._totals_by_author(Comment, comment_ct)

        updated = 0
        for user in User.objects.all():
            new_post = post_totals.get(user.pk, 0)
            new_comment = comment_totals.get(user.pk, 0)
            if user.post_karma != new_post or user.comment_karma != new_comment:
                user.post_karma = new_post
                user.comment_karma = new_comment
                user.save(update_fields=["post_karma", "comment_karma"])
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"Recalculated karma for {updated} user(s)."))

    def _totals_by_author(self, model, ct) -> dict[int, int]:
        target_ids = list(model.objects.values_list("pk", "author_id"))
        author_by_target = dict(target_ids)
        if not author_by_target:
            return {}
        rows = (
            Vote.objects.filter(content_type=ct, object_id__in=author_by_target.keys())
            .values("object_id")
            .annotate(total=Sum("value"))
        )
        totals: dict[int, int] = {}
        for row in rows:
            author_id = author_by_target.get(row["object_id"])
            if author_id is None:
                continue
            totals[author_id] = totals.get(author_id, 0) + (row["total"] or 0)
        return totals

"""Follow counts and viewer relations for user lists."""

from django.db.models import Count, Exists, IntegerField, OuterRef, Subquery
from django.db.models.functions import Coalesce

from .models import Block, Follow


def _count(field: str):
    # Correlated subquery so two counts never share one JOIN/GROUP BY and multiply each other.
    rows = Follow.objects.filter(**{field: OuterRef("pk")}).order_by().values(field)
    return Coalesce(
        Subquery(rows.annotate(n=Count("pk")).values("n"), output_field=IntegerField()), 0
    )


def with_social_annotations(qs, viewer):
    """Annotate follower/following counts, plus the viewer's follow/block flags when authenticated."""
    qs = qs.annotate(
        followers_count=_count("followed"),
        following_count=_count("follower"),
    )
    if not viewer or not viewer.is_authenticated:
        return qs
    return qs.annotate(
        viewer_follows=Exists(Follow.objects.filter(follower=viewer, followed=OuterRef("pk"))),
        viewer_blocks=Exists(Block.objects.filter(blocker=viewer, blocked=OuterRef("pk"))),
    )

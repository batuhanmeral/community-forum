from django.db.models import Count, Prefetch

from .models import PollOption, PollVote


def poll_prefetches(user, prefix: str = "") -> list[Prefetch]:
    """Option vote counts in one query, plus the viewer's own choice for authenticated users."""
    prefetches = [
        Prefetch(f"{prefix}options", PollOption.objects.annotate(vote_count=Count("votes")))
    ]
    if user and user.is_authenticated:
        prefetches.append(
            Prefetch(f"{prefix}votes", PollVote.objects.filter(user=user), to_attr="my_votes")
        )
    return prefetches

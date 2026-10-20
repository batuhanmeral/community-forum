"""Viewer-specific vote and save state for posts and comments."""

from django.db.models import Prefetch


def viewer_prefetches(user) -> list[Prefetch]:
    """Prefetch only the viewer's own votes and saves; none for anonymous requests."""
    if not user or not user.is_authenticated:
        return []
    from apps.saves.models import SavedItem
    from apps.votes.models import Vote

    return [
        Prefetch("votes", Vote.objects.filter(user=user), to_attr="my_votes"),
        Prefetch("saves", SavedItem.objects.filter(user=user), to_attr="my_saves"),
    ]


def viewer_vote(obj, user) -> int | None:
    if not user.is_authenticated:
        return None
    votes = getattr(obj, "my_votes", None)
    # Objects not loaded through the list querysets (create/update responses) lack the prefetch.
    if votes is None:
        votes = obj.votes.filter(user=user)
    vote = next(iter(votes), None)
    return vote.value if vote else None


def viewer_saved(obj, user) -> bool:
    if not user.is_authenticated:
        return False
    saves = getattr(obj, "my_saves", None)
    if saves is None:
        return obj.saves.filter(user=user).exists()
    return bool(saves)

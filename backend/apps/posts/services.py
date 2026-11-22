from django.db.models import Q

from apps.communities.services import is_moderator


def can_see_unapproved(user, post) -> bool:
    return post.author_id == getattr(user, "id", None) or is_moderator(user, post.community)


def root_available(root) -> bool:
    """A crosspost's copied content may be shown only while its original is live."""
    return root.deleted_at is None and root.is_approved


def unavailable_root_q(prefix: str = "") -> Q:
    """Rows that are crossposts of a deleted or held original (API masks them, lists skip them)."""
    root = f"{prefix}crosspost_parent__"
    return Q(**{f"{root}deleted_at__isnull": False}) | Q(**{f"{root}is_approved": False})


def nsfw_q() -> Q:
    """NSFW rows, including crossposts whose original or its community was flagged later."""
    return (
        Q(is_nsfw=True)
        | Q(community__is_nsfw=True)
        | Q(crosspost_parent__is_nsfw=True)
        | Q(crosspost_parent__community__is_nsfw=True)
    )


def effective_nsfw(post) -> bool:
    root = post.crosspost_parent
    return bool(
        post.is_nsfw
        or post.community.is_nsfw
        or (root is not None and (root.is_nsfw or root.community.is_nsfw))
    )


def effective_spoiler(post) -> bool:
    """A copy is a spoiler whenever its original is, even if the original was flagged later."""
    root = post.crosspost_parent
    return bool(post.is_spoiler or (root is not None and root.is_spoiler))

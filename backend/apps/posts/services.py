from apps.communities.services import is_moderator


def can_see_unapproved(user, post) -> bool:
    return post.author_id == getattr(user, "id", None) or is_moderator(user, post.community)

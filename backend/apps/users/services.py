from django.db import transaction
from django.utils import timezone

from apps.comments.models import Comment
from apps.communities.models import Community, Membership
from apps.messaging.models import Message
from apps.notifications.models import Notification
from apps.posts.models import Post
from apps.saves.models import SavedItem
from apps.social.models import Block, Follow
from apps.votes.models import Vote

from .models import User


def deleted_username(user: User) -> str:
    # The hyphen is outside the sign-up alphabet, so no new account can claim this name.
    return f"deleted-{user.pk}"


def delete_file_on_commit(field_file) -> None:
    """Remove an upload only once the row change that dropped it is durable."""
    if not field_file:
        return
    storage, name = field_file.storage, field_file.name
    transaction.on_commit(lambda: storage.delete(name))


def _hand_over_communities(user: User) -> None:
    # Only the creator can appoint admins, so a deleted creator would freeze the community for good.
    rank = {Membership.Role.ADMIN: 0, Membership.Role.MODERATOR: 1, Membership.Role.MEMBER: 2}
    for community in Community.objects.select_for_update().filter(creator=user):
        candidates = (
            Membership.objects.filter(community=community, is_banned=False, user__is_active=True)
            .exclude(user=user)
            .order_by("joined_at")
        )
        heir = min(candidates, key=lambda m: rank[m.role], default=None)
        if heir is None:
            continue
        community.creator_id = heir.user_id
        community.save(update_fields=["creator"])
        heir.role = Membership.Role.ADMIN
        heir.save(update_fields=["role"])


@transaction.atomic
def delete_account(user: User) -> None:
    """Erase personal data (KVKK/GDPR) but keep the row: content, votes and created communities point at it."""
    # Locked so a profile update that loaded the row earlier can't write the old data back.
    user = User.objects.select_for_update().get(pk=user.pk)
    _hand_over_communities(user)
    delete_file_on_commit(user.avatar)
    user.username = deleted_username(user)
    user.email = ""
    user.email_verified = False
    user.first_name = ""
    user.last_name = ""
    user.bio = ""
    user.avatar = None
    user.show_nsfw = False
    user.is_active = False
    # Changes the password hash, which revokes every outstanding token (CHECK_REVOKE_TOKEN).
    user.set_unusable_password()
    user.save()
    Follow.objects.filter(follower=user).delete()
    Follow.objects.filter(followed=user).delete()
    Block.objects.filter(blocker=user).delete()
    Block.objects.filter(blocked=user).delete()
    SavedItem.objects.filter(user=user).delete()
    Notification.objects.filter(recipient=user).delete()
    Membership.objects.filter(user=user).delete()


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def export_account(user: User) -> dict:
    """Everything the account holder wrote or chose, as plain JSON (KVKK/GDPR right of access)."""
    return {
        "exported_at": _iso(timezone.now()),
        "profile": {
            "username": user.username,
            "email": user.email,
            "email_verified": user.email_verified,
            "bio": user.bio,
            "date_joined": _iso(user.date_joined),
            "post_karma": user.post_karma,
            "comment_karma": user.comment_karma,
            "show_nsfw": user.show_nsfw,
        },
        "posts": [
            {
                "id": p.id,
                "community": p.community.slug,
                "title": p.title,
                "body": p.body,
                "url": p.url,
                "created_at": _iso(p.created_at),
                "deleted_at": _iso(p.deleted_at),
            }
            for p in Post.objects.filter(author=user).select_related("community").order_by("id")
        ],
        "comments": [
            {
                "id": c.id,
                "post_id": c.post_id,
                "body": c.body,
                "created_at": _iso(c.created_at),
                "deleted_at": _iso(c.deleted_at),
            }
            for c in Comment.objects.filter(author=user).order_by("id")
        ],
        "messages_sent": [
            {"conversation_id": m.conversation_id, "body": m.body, "created_at": _iso(m.created_at)}
            for m in Message.objects.filter(sender=user).order_by("id")
        ],
        "votes": [
            {"target": v.content_type.model, "target_id": v.object_id, "value": v.value}
            for v in Vote.objects.filter(user=user).select_related("content_type").order_by("id")
        ],
        "saved": [
            {"target": s.content_type.model, "target_id": s.object_id}
            for s in SavedItem.objects.filter(user=user).select_related("content_type")
        ],
        "following": list(
            Follow.objects.filter(follower=user).values_list("followed__username", flat=True)
        ),
        "blocked": list(
            Block.objects.filter(blocker=user).values_list("blocked__username", flat=True)
        ),
        "memberships": [
            {"community": m.community.slug, "role": m.role, "joined_at": _iso(m.joined_at)}
            for m in Membership.objects.filter(user=user).select_related("community")
        ],
    }

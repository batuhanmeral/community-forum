"""Question & answer rules: accepted answers, the +15 karma grant and bounties.

Every karma movement is a KarmaAdjustment row, and the same amount is applied to
`User.comment_karma`, so `recalculate_karma` (votes + adjustments) always agrees with the
live counters. Bounty holds are charged with a conditional UPDATE so two concurrent
requests can never spend the same karma twice or push the balance below zero.
"""

from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.comments.models import Comment
from apps.communities.services import is_banned, is_moderator
from apps.notifications.services import notify
from apps.users.models import KarmaAdjustment, User

from .models import Post

ACCEPT_BONUS = 15
BOUNTY_MIN = 50
BOUNTY_MAX = 500
BOUNTY_STEP = 50
BOUNTY_DAYS = 7

BOUNTY_OPEN = "open"
BOUNTY_PAID = "paid"
BOUNTY_REFUNDED = "refunded"


def _lock_post(post_id: int) -> Post:
    return Post.objects.select_for_update().select_related("community").get(pk=post_id)


def _credit(user_id: int, amount: int, *, reason: str, post=None, comment=None, **extra):
    KarmaAdjustment.objects.create(
        user_id=user_id, amount=amount, reason=reason, post=post, comment=comment, **extra
    )
    User.objects.filter(pk=user_id).update(comment_karma=F("comment_karma") + amount)


def _revoke_grant(comment_id: int) -> None:
    grant = (
        KarmaAdjustment.objects.select_for_update()
        .filter(comment_id=comment_id, reason="answer_accepted", active=True)
        .first()
    )
    if grant is None:
        return
    grant.active = False
    grant.save(update_fields=["active"])
    _credit(
        grant.user_id,
        -grant.amount,
        reason="answer_unaccepted",
        post=grant.post,
        comment_id=comment_id,
        reverses=grant,
    )


def _check_can_manage(actor, post: Post) -> None:
    if not post.is_question or post.deleted_at is not None or not post.is_approved:
        raise ValidationError("This post is not an open question.")
    if is_banned(actor, post.community):
        raise PermissionDenied("You are banned from this community.")
    if post.author_id != actor.pk and not is_moderator(actor, post.community):
        raise PermissionDenied("Only the asker or a moderator can do this.")


def accept_answer(actor, post_id: int, comment_id) -> Post:
    with transaction.atomic():
        post = _lock_post(post_id)
        _check_can_manage(actor, post)
        try:
            comment = Comment.objects.get(pk=comment_id, post_id=post.pk, deleted_at__isnull=True)
        except (Comment.DoesNotExist, TypeError, ValueError):
            raise ValidationError({"comment": "Pick a comment on this question."}) from None
        if comment.author_id == post.author_id:
            raise ValidationError({"comment": "The asker cannot accept their own answer."})
        if comment.author_id == actor.pk:
            # A moderator accepting their own answer would award themselves the karma and bounty.
            raise ValidationError({"comment": "You cannot accept your own answer."})
        if post.accepted_comment_id == comment.pk:
            return post
        if post.bounty_status == BOUNTY_PAID:
            raise ValidationError("A paid bounty locks the accepted answer.")
        if post.accepted_comment_id:
            _revoke_grant(post.accepted_comment_id)
        post.accepted_comment = comment
        update_fields = ["accepted_comment"]
        _credit(
            comment.author_id,
            ACCEPT_BONUS,
            reason="answer_accepted",
            post=post,
            comment=comment,
            active=True,
        )
        bounty = 0
        refunded = False
        if post.bounty_status == BOUNTY_OPEN and post.bounty_expires_at <= timezone.now():
            # An expired bounty is the asker's again, even if the sweep has not run yet.
            refunded = _refund_locked(post)
        if post.bounty_status == BOUNTY_OPEN:
            bounty = post.bounty_amount
            _credit(comment.author_id, bounty, reason="bounty_award", post=post, comment=comment)
            post.bounty_status = BOUNTY_PAID
            update_fields.append("bounty_status")
        post.save(update_fields=update_fields)
    answerer = comment.author
    notify(answerer, actor=actor, verb="answer_accepted", target=comment, community=post.community)
    if bounty:
        notify(
            answerer, actor=actor, verb="bounty_awarded", target=comment, community=post.community
        )
    if refunded:
        notify(post.author, verb="bounty_refunded", target=post, community=post.community)
    return post


def unaccept_answer(actor, post_id: int) -> Post:
    with transaction.atomic():
        post = _lock_post(post_id)
        _check_can_manage(actor, post)
        if post.bounty_status == BOUNTY_PAID:
            raise ValidationError("A paid bounty locks the accepted answer.")
        if post.accepted_comment_id:
            _revoke_grant(post.accepted_comment_id)
            post.accepted_comment = None
            post.save(update_fields=["accepted_comment"])
    return post


def place_bounty(actor, post_id: int, amount) -> Post:
    if (
        isinstance(amount, bool)
        or not isinstance(amount, int)
        or not BOUNTY_MIN <= amount <= BOUNTY_MAX
        or amount % BOUNTY_STEP
    ):
        raise ValidationError(
            {"amount": f"Bounties are {BOUNTY_MIN}-{BOUNTY_MAX} karma in steps of {BOUNTY_STEP}."}
        )
    with transaction.atomic():
        post = _lock_post(post_id)
        if post.author_id != actor.pk:
            raise PermissionDenied("Only the asker can offer a bounty.")
        _check_can_manage(actor, post)
        if post.bounty_status or post.accepted_comment_id:
            raise ValidationError("This question already has a bounty or an accepted answer.")
        # Conditional UPDATE: the balance check and the charge are one statement.
        charged = User.objects.filter(
            pk=actor.pk, post_karma__gte=amount - F("comment_karma")
        ).update(comment_karma=F("comment_karma") - amount)
        if not charged:
            raise ValidationError({"amount": "Not enough karma."})
        KarmaAdjustment.objects.create(
            user_id=actor.pk, amount=-amount, reason="bounty_hold", post=post
        )
        post.bounty_amount = amount
        post.bounty_status = BOUNTY_OPEN
        post.bounty_expires_at = timezone.now() + timedelta(days=BOUNTY_DAYS)
        post.save(update_fields=["bounty_amount", "bounty_status", "bounty_expires_at"])
    return post


def _refund_locked(post: Post) -> bool:
    """Refund an open bounty on a row the caller holds locked. Only an OPEN bounty pays back."""
    if post.bounty_status != BOUNTY_OPEN:
        return False
    post.bounty_status = BOUNTY_REFUNDED
    post.save(update_fields=["bounty_status"])
    _credit(post.author_id, post.bounty_amount, reason="bounty_refund", post=post)
    return True


def refund_bounty(post_id: int) -> bool:
    """Return an open bounty to the asker. Idempotent: only the first call pays."""
    with transaction.atomic():
        post = _lock_post(post_id)
        refunded = _refund_locked(post)
    if refunded:
        notify(post.author, verb="bounty_refunded", target=post, community=post.community)
    return refunded


def on_comment_hard_delete(comment_id: int, *, reverse_karma: bool = True) -> None:
    """Reverse the +15 grant before an accepted comment row disappears (admin/cascade delete).

    An active grant must not outlive its comment (qa_valid_active_grant). When the answerer
    themselves is being deleted their ledger goes with them, so the grant is only deactivated.
    """
    with transaction.atomic():
        if reverse_karma:
            _revoke_grant(comment_id)
        else:
            KarmaAdjustment.objects.filter(
                comment_id=comment_id, reason="answer_accepted", active=True
            ).update(active=False)


def on_post_hard_delete(post_id: int) -> None:
    """An open bounty on a post that is being removed for good goes back to the asker."""
    with transaction.atomic():
        post = Post.objects.select_for_update().filter(pk=post_id).first()
        if post is not None:
            _refund_locked(post)


def expire_bounties() -> int:
    due = Post.objects.filter(bounty_status=BOUNTY_OPEN).filter(
        bounty_expires_at__lte=timezone.now()
    ) | Post.objects.filter(bounty_status=BOUNTY_OPEN, deleted_at__isnull=False)
    return sum(refund_bounty(pk) for pk in due.values_list("pk", flat=True))


def with_bounty_held(users):
    """Annotate `held_bounty_karma`: karma each user has locked in open bounties.

    The hold is charged to comment_karma, so profiles show it separately instead of letting it
    look like negative comment karma.
    """
    from django.db.models import IntegerField, OuterRef, Subquery, Sum
    from django.db.models.functions import Coalesce

    held = (
        Post.objects.filter(author=OuterRef("pk"), bounty_status=BOUNTY_OPEN)
        .order_by()
        .values("author")
        .annotate(total=Sum("bounty_amount"))
        .values("total")
    )
    return users.annotate(
        held_bounty_karma=Coalesce(Subquery(held, output_field=IntegerField()), 0)
    )


def bounty_held(user) -> int:
    from django.db.models import Sum

    total = Post.objects.filter(author=user, bounty_status=BOUNTY_OPEN).aggregate(
        total=Sum("bounty_amount")
    )["total"]
    return total or 0

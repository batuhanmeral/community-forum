"""Q&A state must survive races with edits, deletes and the expiry sweep."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from django.contrib.auth import get_user_model
from django.db.models import Sum

from apps.comments.models import Comment
from apps.communities.models import Community
from apps.posts import qa as qa_service
from apps.posts.models import Post
from apps.posts.views import PostDetailView
from apps.users.models import KarmaAdjustment

from .test_qa import accept, bounty, question, unaccept

User = get_user_model()


def _karma_matches_ledger(user):
    user.refresh_from_db()
    ledger = KarmaAdjustment.objects.filter(user=user).aggregate(s=Sum("amount"))["s"] or 0
    return user.comment_karma == ledger


def _race_patch(monkeypatch, between):
    """Run `between()` after the PATCH view has loaded the post but before it saves."""
    original = PostDetailView.get_object

    def get_object(self):
        post = original(self)
        between()
        return post

    monkeypatch.setattr(PostDetailView, "get_object", get_object)


@pytest.mark.django_db
class TestEditRaces:
    def test_patch_racing_accept_keeps_payout_and_lock(self, qa, monkeypatch):
        api, owner, answerer, other, _ = qa
        post, comment = question(qa)
        User.objects.filter(pk=owner.pk).update(post_karma=100)
        assert bounty(api, post).status_code == 200
        _race_patch(monkeypatch, lambda: qa_service.accept_answer(owner, post.pk, comment.pk))
        response = api.patch(f"/api/v1/posts/{post.pk}/", {"title": "Why, really?"}, format="json")
        assert response.status_code == 200
        post.refresh_from_db()
        assert post.title == "Why, really?"
        assert post.accepted_comment_id == comment.pk
        assert post.bounty_status == qa_service.BOUNTY_PAID
        monkeypatch.undo()
        second = Comment.objects.create(post=post, author=other, body="Also.")
        assert accept(api, post, second).status_code == 400
        assert KarmaAdjustment.objects.filter(reason="bounty_award").count() == 1
        assert _karma_matches_ledger(answerer)

    def test_patch_racing_bounty_keeps_the_hold_refundable(self, qa, monkeypatch):
        api, owner, _, _, _ = qa
        post, _ = question(qa)
        User.objects.filter(pk=owner.pk).update(post_karma=100)
        _race_patch(monkeypatch, lambda: qa_service.place_bounty(owner, post.pk, 50))
        assert (
            api.patch(f"/api/v1/posts/{post.pk}/", {"title": "Edited"}, format="json").status_code
            == 200
        )
        post.refresh_from_db()
        assert post.bounty_status == qa_service.BOUNTY_OPEN
        assert post.bounty_amount == 50
        assert post.bounty_expires_at is not None
        assert qa_service.refund_bounty(post.pk) is True
        owner.refresh_from_db()
        assert owner.comment_karma == 0


@pytest.mark.django_db
def test_moderator_cannot_accept_their_own_answer_or_take_the_bounty(qa):
    from apps.communities.models import Membership

    api, owner, _, other, community = qa
    post, _ = question(qa)
    User.objects.filter(pk=owner.pk).update(post_karma=100)
    assert bounty(api, post).status_code == 200
    Membership.objects.create(user=other, community=community, role="moderator")
    own = Comment.objects.create(post=post, author=other, body="Mine.")
    api.force_authenticate(other)
    assert accept(api, post, own).status_code == 400
    post.refresh_from_db()
    assert post.accepted_comment_id is None
    assert post.bounty_status == qa_service.BOUNTY_OPEN
    other.refresh_from_db()
    assert other.comment_karma == 0


def _accepted_with_open_bounty_elsewhere(qa):
    """An accepted answer, plus a second question by the same asker with an open bounty."""
    api, owner, _, _, _ = qa
    User.objects.filter(pk=owner.pk).update(post_karma=200)
    post, comment = question(qa)
    assert accept(api, post, comment).status_code == 200
    held, _ = question(qa)
    assert bounty(api, held).status_code == 200
    return post, comment, held


@pytest.mark.django_db
class TestHardDeletes:
    def test_hard_deleting_the_accepted_comment_reverses_the_grant(self, qa):
        _, _, answerer, _, _ = qa
        post, comment, _ = _accepted_with_open_bounty_elsewhere(qa)
        Comment.objects.filter(pk=comment.pk).delete()
        post.refresh_from_db()
        assert post.accepted_comment_id is None
        assert not KarmaAdjustment.objects.filter(active=True).exists()
        answerer.refresh_from_db()
        assert answerer.comment_karma == 0
        assert _karma_matches_ledger(answerer)

    def test_hard_deleting_a_post_refunds_its_open_bounty(self, qa):
        _, owner, answerer, _, _ = qa
        post, _, held = _accepted_with_open_bounty_elsewhere(qa)
        held.delete()
        owner.refresh_from_db()
        assert owner.comment_karma == 0
        assert KarmaAdjustment.objects.filter(reason="bounty_refund", user=owner).count() == 1
        assert _karma_matches_ledger(owner)
        post.delete()
        assert _karma_matches_ledger(answerer)
        answerer.refresh_from_db()
        assert answerer.comment_karma == 0

    def test_hard_deleting_the_community(self, qa):
        _, owner, answerer, _, community = qa
        _accepted_with_open_bounty_elsewhere(qa)
        community.delete()
        owner.refresh_from_db()
        assert owner.comment_karma == 0
        assert _karma_matches_ledger(owner)
        assert _karma_matches_ledger(answerer)

    def test_hard_deleting_the_answerer(self, qa):
        _, owner, answerer, _, _ = qa
        post, _, _ = _accepted_with_open_bounty_elsewhere(qa)
        answerer.delete()
        post.refresh_from_db()
        assert post.accepted_comment_id is None
        assert _karma_matches_ledger(owner)

    def test_hard_deleting_the_asker(self, qa):
        _, owner, answerer, other, community = qa
        _accepted_with_open_bounty_elsewhere(qa)
        Community.objects.filter(pk=community.pk).update(creator=other)
        owner.delete()
        assert not Post.objects.exists()
        answerer.refresh_from_db()
        assert answerer.comment_karma == 0
        assert _karma_matches_ledger(answerer)


@pytest.mark.django_db
class TestBountyLifecycleGuards:
    def _paid(self, qa):
        api, owner, _, _, _ = qa
        User.objects.filter(pk=owner.pk).update(post_karma=100)
        post, comment = question(qa)
        assert bounty(api, post).status_code == 200
        assert accept(api, post, comment).status_code == 200
        return post, comment

    def test_deleting_after_payout_does_not_refund(self, qa):
        api, owner, _, _, _ = qa
        post, _ = self._paid(qa)
        assert api.delete(f"/api/v1/posts/{post.pk}/").status_code == 204
        assert qa_service.refund_bounty(post.pk) is False
        assert not KarmaAdjustment.objects.filter(reason="bounty_refund").exists()
        owner.refresh_from_db()
        assert owner.comment_karma == -50

    def test_a_paid_bounty_locks_the_accepted_answer(self, qa):
        api, _, answerer, other, _ = qa
        post, comment = self._paid(qa)
        second = Comment.objects.create(post=post, author=other, body="Better.")
        assert accept(api, post, second).status_code == 400
        assert unaccept(api, post).status_code == 400
        post.refresh_from_db()
        assert post.accepted_comment_id == comment.pk
        other.refresh_from_db()
        assert other.comment_karma == 0
        answerer.refresh_from_db()
        assert answerer.comment_karma == 65

    def test_deleting_the_question_refunds_an_open_bounty_at_once(self, qa):
        api, owner, _, _, _ = qa
        User.objects.filter(pk=owner.pk).update(post_karma=100)
        post, _ = question(qa)
        assert bounty(api, post).status_code == 200
        assert api.delete(f"/api/v1/posts/{post.pk}/").status_code == 204
        post.refresh_from_db()
        assert post.bounty_status == qa_service.BOUNTY_REFUNDED
        owner.refresh_from_db()
        assert owner.comment_karma == 0


def _in_threads(*calls):
    """Run the calls concurrently; any exception is re-raised, never swallowed."""
    from django.db import connection

    def run(call):
        try:
            return call()
        finally:
            connection.close()

    with ThreadPoolExecutor(len(calls)) as pool:
        futures = [pool.submit(run, call) for call in calls]
        return [future.result() for future in futures]


def _slow_lock(monkeypatch):
    """Hold each locked read open a moment so concurrent calls overlap unless the row lock
    serialises them (this is what makes the race tests fail without select_for_update)."""
    import time

    real = qa_service._lock_post

    def slow(post_id):
        post = real(post_id)
        time.sleep(0.2)
        return post

    monkeypatch.setattr(qa_service, "_lock_post", slow)


@pytest.mark.django_db(transaction=True)
def test_concurrent_accepts_of_two_answers_leave_one_grant(qa, monkeypatch):
    _, owner, answerer, other, _ = qa
    post, comment = question(qa)
    second = Comment.objects.create(post=post, author=other, body="Me too.")
    _slow_lock(monkeypatch)
    _in_threads(
        lambda: qa_service.accept_answer(owner, post.pk, comment.pk),
        lambda: qa_service.accept_answer(owner, post.pk, second.pk),
    )
    post.refresh_from_db()
    assert post.accepted_comment_id in (comment.pk, second.pk)
    grants = KarmaAdjustment.objects.filter(reason="answer_accepted", active=True)
    assert list(grants.values_list("comment_id", flat=True)) == [post.accepted_comment_id]
    assert _karma_matches_ledger(answerer) and _karma_matches_ledger(other)
    answerer.refresh_from_db()
    other.refresh_from_db()
    assert answerer.comment_karma + other.comment_karma == 15


@pytest.mark.django_db(transaction=True)
def test_concurrent_accept_and_unaccept_keep_one_consistent_grant(qa, monkeypatch):
    _, owner, answerer, _, _ = qa
    post, comment = question(qa)
    _slow_lock(monkeypatch)
    for _ in range(3):
        _in_threads(
            lambda: qa_service.accept_answer(owner, post.pk, comment.pk),
            lambda: qa_service.unaccept_answer(owner, post.pk),
        )
        post.refresh_from_db()
        active = KarmaAdjustment.objects.filter(comment=comment, active=True).count()
        assert active == (1 if post.accepted_comment_id else 0)
        answerer.refresh_from_db()
        assert answerer.comment_karma == 15 * active
        assert _karma_matches_ledger(answerer)


def _expired_bounty(qa):
    from datetime import timedelta

    from django.utils import timezone

    api, owner, _, _, _ = qa
    User.objects.filter(pk=owner.pk).update(post_karma=100)
    post, comment = question(qa)
    assert bounty(api, post).status_code == 200
    Post.objects.filter(pk=post.pk).update(bounty_expires_at=timezone.now() - timedelta(seconds=1))
    return post, comment


@pytest.mark.django_db
def test_accepting_after_expiry_refunds_instead_of_paying(qa):
    api, owner, answerer, _, _ = qa
    post, comment = _expired_bounty(qa)
    assert accept(api, post, comment).status_code == 200
    post.refresh_from_db()
    assert post.accepted_comment_id == comment.pk
    assert post.bounty_status == qa_service.BOUNTY_REFUNDED
    answerer.refresh_from_db()
    assert answerer.comment_karma == 15
    owner.refresh_from_db()
    assert owner.comment_karma == 0
    from apps.notifications.models import Notification

    assert Notification.objects.filter(recipient=owner, verb="bounty_refunded").count() == 1


@pytest.mark.django_db(transaction=True)
def test_accept_racing_the_expiry_sweep_settles_the_bounty_once(qa):
    _, owner, answerer, _, _ = qa
    post, comment = _expired_bounty(qa)
    _in_threads(
        lambda: qa_service.accept_answer(owner, post.pk, comment.pk),
        qa_service.expire_bounties,
    )
    assert not KarmaAdjustment.objects.filter(reason="bounty_award").exists()
    assert KarmaAdjustment.objects.filter(reason="bounty_refund").count() == 1
    assert _karma_matches_ledger(owner) and _karma_matches_ledger(answerer)
    owner.refresh_from_db()
    assert owner.comment_karma == 0


@pytest.mark.django_db
def test_a_soft_deleted_accepted_answer_is_not_pinned(qa):
    from datetime import timedelta

    from django.utils import timezone

    api, _, _, other, _ = qa
    post, comment = question(qa)
    assert accept(api, post, comment).status_code == 200
    newer = Comment.objects.create(post=post, author=other, body="Later.")
    Comment.objects.filter(pk=newer.pk).update(created_at=timezone.now() + timedelta(minutes=1))
    url = f"/api/v1/posts/{post.pk}/comments/?sort=new"
    assert api.get(url).data["results"][0]["id"] == comment.pk
    Comment.objects.filter(pk=comment.pk).update(deleted_at=timezone.now())
    assert api.get(url).data["results"][0]["id"] == newer.pk


@pytest.mark.django_db
def test_profile_reports_the_karma_held_in_open_bounties(qa):
    from rest_framework.test import APIClient

    api, owner, _, _, _ = qa
    User.objects.filter(pk=owner.pk).update(post_karma=150)
    post, comment = question(qa)
    anon = APIClient()

    def profile():
        return anon.get(f"/api/v1/users/{owner.username}/").data

    assert profile()["bounty_held"] == 0
    assert bounty(api, post).status_code == 200
    data = profile()
    assert data["bounty_held"] == 50
    assert data["comment_karma"] == -50 and data["total_karma"] == 100
    board = {row["username"]: row for row in anon.get("/api/v1/users/leaderboard/").data}
    assert board[owner.username]["bounty_held"] == 50
    assert accept(api, post, comment).status_code == 200
    assert profile()["bounty_held"] == 0
    assert api.get("/api/v1/users/me/").data["bounty_held"] == 0

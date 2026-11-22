from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db.models import Sum
from django.utils import timezone

from apps.comments.models import Comment
from apps.communities.models import Membership
from apps.posts.models import Post

User = get_user_model()


def question(qa):
    api, owner, answerer, other, community = qa
    response = api.post(
        f"/api/v1/communities/{community.slug}/posts/",
        {
            "title": "Why?",
            "kind": "text",
            "is_question": True,
        },
        format="json",
    )
    assert response.status_code == 201
    assert response.data["is_question"] is True
    post = Post.objects.get(pk=response.data["id"])
    comment = Comment.objects.create(post=post, author=answerer, body="Because.")
    return post, comment


def accept(api, post, comment):
    return api.post(f"/api/v1/posts/{post.pk}/accept/", {"comment": comment.pk}, format="json")


def unaccept(api, post):
    return api.delete(f"/api/v1/posts/{post.pk}/accept/")


def bounty(api, post, amount=50):
    return api.post(f"/api/v1/posts/{post.pk}/bounty/", {"amount": amount}, format="json")


@pytest.mark.django_db
class TestQuestions:
    def test_create_question(self, qa):
        question(qa)

    def test_accept_reaccept_net_bonus_and_recalculate(self, qa):
        from apps.users.models import KarmaAdjustment

        api, _, answerer, _, _ = qa
        post, comment = question(qa)
        assert accept(api, post, comment).status_code == 200
        answerer.refresh_from_db()
        assert answerer.comment_karma == 15
        assert unaccept(api, post).status_code == 200
        answerer.refresh_from_db()
        assert answerer.comment_karma == 0
        assert accept(api, post, comment).status_code == 200
        assert accept(api, post, comment).status_code == 200
        assert KarmaAdjustment.objects.filter(user=answerer).aggregate(s=Sum("amount"))["s"] == 15
        call_command("recalculate_karma")
        answerer.refresh_from_db()
        assert answerer.comment_karma == 15
        assert KarmaAdjustment.objects.filter(comment=comment, active=True).count() == 1

    def test_question_only_text_and_enabled_community(self, qa):
        api, _, _, _, community = qa
        url = f"/api/v1/communities/{community.slug}/posts/"
        assert (
            api.post(
                url,
                {
                    "title": "Link",
                    "kind": "link",
                    "url": "https://example.com",
                    "is_question": True,
                },
                format="json",
            ).status_code
            == 400
        )
        community.qa_enabled = False
        community.save()
        assert (
            api.post(url, {"title": "Question", "is_question": True}, format="json").status_code
            == 400
        )

    def test_permissions_self_foreign_deleted_and_nonquestion(self, qa):
        api, owner, answerer, other, community = qa
        post, comment = question(qa)
        api.force_authenticate(other)
        assert accept(api, post, comment).status_code == 403
        api.force_authenticate(owner)
        self_answer = Comment.objects.create(post=post, author=owner, body="Self")
        assert accept(api, post, self_answer).status_code == 400
        another = Post.objects.create(author=owner, community=community, title="Elsewhere")
        foreign = Comment.objects.create(post=another, author=answerer, body="Foreign")
        assert accept(api, post, foreign).status_code == 400
        assert accept(api, another, foreign).status_code == 400
        comment.deleted_at = timezone.now()
        comment.save()
        assert accept(api, post, comment).status_code == 400

    def test_switch_and_pin_nested_once_for_all_sorts(self, qa):
        api, _, answerer, other, _ = qa
        post, first = question(qa)
        nested = Comment.objects.create(post=post, parent=first, author=other, body="Nested")
        assert accept(api, post, first).status_code == 200
        assert accept(api, post, nested).status_code == 200
        answerer.refresh_from_db()
        other.refresh_from_db()
        assert (answerer.comment_karma, other.comment_karma) == (0, 15)
        for sort in ["top", "new", "old", "best", "controversial"]:
            rows = api.get(f"/api/v1/posts/{post.pk}/comments/?sort={sort}").data["results"]
            assert rows[0]["id"] == nested.pk
            assert rows[0]["is_accepted"] is True
            assert [row["id"] for row in rows].count(nested.pk) == 1

    def test_bounty_payment_idempotent_and_locks_answer(self, qa):
        api, owner, answerer, _, _ = qa
        post, comment = question(qa)
        User.objects.filter(pk=owner.pk).update(post_karma=100)
        assert bounty(api, post).status_code == 200
        assert bounty(api, post).status_code == 400
        owner.refresh_from_db()
        assert owner.post_karma + owner.comment_karma == 50
        assert accept(api, post, comment).status_code == 200
        assert accept(api, post, comment).status_code == 200
        answerer.refresh_from_db()
        assert answerer.comment_karma == 65
        assert unaccept(api, post).status_code == 400
        post.refresh_from_db()
        assert post.accepted_comment_id == comment.pk

    @pytest.mark.parametrize("amount", [0, 49, 51, 550, "bad", True])
    def test_bounty_rejects_invalid_amounts(self, qa, amount):
        post, _ = question(qa)
        assert bounty(qa[0], post, amount).status_code == 400

    def test_bounty_insufficient_balance(self, qa):
        post, _ = question(qa)
        assert bounty(qa[0], post).status_code == 400

    def test_bounty_expiry_refunds_once(self, qa):
        api, owner, _, _, _ = qa
        post, _ = question(qa)
        User.objects.filter(pk=owner.pk).update(post_karma=100)
        assert bounty(api, post).status_code == 200
        Post.objects.filter(pk=post.pk).update(
            bounty_expires_at=timezone.now() - timedelta(seconds=1)
        )
        call_command("expire_bounties")
        call_command("expire_bounties")
        owner.refresh_from_db()
        assert owner.post_karma + owner.comment_karma == 100

    def test_delete_refunds_once(self, qa):
        api, owner, _, _, _ = qa
        post, _ = question(qa)
        User.objects.filter(pk=owner.pk).update(post_karma=100)
        assert bounty(api, post).status_code == 200
        assert api.delete(f"/api/v1/posts/{post.pk}/").status_code == 204
        call_command("expire_bounties")
        owner.refresh_from_db()
        assert owner.post_karma + owner.comment_karma == 100

    def test_answered_filter_only_includes_questions(self, qa):
        api, owner, _, _, community = qa
        post, comment = question(qa)
        Post.objects.create(author=owner, community=community, title="Ordinary")
        url = "/api/v1/feed/?scope=all&answered=false"
        assert [row["id"] for row in api.get(url).data["results"]] == [post.pk]
        assert accept(api, post, comment).status_code == 200
        assert api.get(url).data["results"] == []
        assert api.get("/api/v1/feed/?scope=all&answered=true").data["results"][0]["id"] == post.pk


@pytest.mark.django_db
class TestQaNotificationsAndAccess:
    def test_notifications_for_accept_award_and_refund(self, qa):
        from apps.notifications.models import Notification

        api, owner, answerer, _, _ = qa
        post, comment = question(qa)
        User.objects.filter(pk=owner.pk).update(post_karma=100)
        bounty(api, post)
        accept(api, post, comment)
        verbs = set(Notification.objects.filter(recipient=answerer).values_list("verb", flat=True))
        assert verbs == {"answer_accepted", "bounty_awarded"}
        second, _ = question(qa)
        bounty(api, second)
        Post.objects.filter(pk=second.pk).update(bounty_expires_at=timezone.now())
        call_command("expire_bounties")
        assert Notification.objects.filter(recipient=owner, verb="bounty_refunded").count() == 1

    def test_blocked_asker_notification_is_skipped(self, qa):
        from apps.notifications.models import Notification
        from apps.social.models import Block

        api, owner, answerer, _, _ = qa
        post, comment = question(qa)
        Block.objects.create(blocker=answerer, blocked=owner)
        assert accept(api, post, comment).status_code == 200
        assert not Notification.objects.filter(recipient=answerer).exists()

    def test_moderator_can_accept_and_clear(self, qa):
        api, owner, answerer, other, community = qa
        post, comment = question(qa)
        Membership.objects.create(user=other, community=community, role="moderator")
        api.force_authenticate(other)
        assert accept(api, post, comment).status_code == 200
        assert unaccept(api, post).status_code == 200

    def test_banned_moderator_and_anonymous_are_refused(self, qa):
        api, _, _, other, community = qa
        post, comment = question(qa)
        Membership.objects.create(user=other, community=community, role="moderator", is_banned=True)
        api.force_authenticate(other)
        assert accept(api, post, comment).status_code == 403
        api.force_authenticate(None)
        assert accept(api, post, comment).status_code == 401

    def test_only_asker_places_bounty(self, qa):
        api, _, _, other, _ = qa
        post, _ = question(qa)
        User.objects.filter(pk=other.pk).update(post_karma=500)
        api.force_authenticate(other)
        assert bounty(api, post).status_code == 403

    def test_bounty_refused_on_non_question_and_after_accept(self, qa):
        api, owner, _, _, community = qa
        User.objects.filter(pk=owner.pk).update(post_karma=500)
        ordinary = Post.objects.create(author=owner, community=community, title="Plain")
        assert bounty(api, ordinary).status_code == 400
        post, comment = question(qa)
        accept(api, post, comment)
        assert bounty(api, post).status_code == 400


@pytest.mark.django_db(transaction=True)
def test_concurrent_bounties_cannot_overspend(qa):
    from concurrent.futures import ThreadPoolExecutor

    from django.db import connection

    from apps.posts import qa as qa_service

    _, owner, _, _, community = qa
    User.objects.filter(pk=owner.pk).update(post_karma=60)
    posts = [
        Post.objects.create(author=owner, community=community, title=f"Q{i}", is_question=True)
        for i in range(4)
    ]

    def place(post):
        try:
            qa_service.place_bounty(owner, post.pk, 50)
            return True
        except Exception:
            return False
        finally:
            connection.close()

    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(place, posts))
    owner.refresh_from_db()
    assert results.count(True) == 1
    assert owner.post_karma + owner.comment_karma == 10

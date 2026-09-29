import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.comments.models import Comment
from apps.communities.models import Community, Membership
from apps.polls.models import Poll, PollOption
from apps.posts.models import Post

User = get_user_model()
VOTE = reverse("api_v1:votes:vote")


def membership_url(slug):
    return reverse("api_v1:communities:community-membership", args=[slug])


def detail_url(slug):
    return reverse("api_v1:communities:community-detail", args=[slug])


def comments_url(post_id):
    return reverse("api_v1:post-comments:post-comments", args=[post_id])


def poll_vote_url(poll_id):
    return reverse("api_v1:polls:poll-vote", args=[poll_id])


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def owner(db):
    return User.objects.create_user(username="owner", email="o@x.com", password="StrongPass123!")


@pytest.fixture
def banned(db):
    return User.objects.create_user(username="banned", email="b@x.com", password="StrongPass123!")


@pytest.fixture
def community(owner, banned):
    c = Community.objects.create(slug="py", name="Py", creator=owner)
    Membership.objects.create(user=banned, community=c, is_banned=True)
    return c


@pytest.fixture
def post(owner, community):
    return Post.objects.create(author=owner, community=community, title="t")


@pytest.mark.django_db
class TestBanSticks:
    def test_leaving_keeps_the_ban(self, api, banned, community):
        api.force_authenticate(banned)
        assert api.delete(membership_url("py")).status_code == 400
        assert Membership.objects.get(user=banned, community=community).is_banned
        assert api.post(membership_url("py")).status_code == 400

    def test_banned_user_is_not_a_member(self, api, banned, community):
        api.force_authenticate(banned)
        data = api.get(detail_url("py")).data
        assert data["is_member"] is False
        assert data["is_banned"] is True
        assert data["my_role"] is None
        assert data["member_count"] == 1  # only the creator

    def test_banned_moderator_does_not_see_banned_keywords(self, api, banned, community):
        Membership.objects.filter(user=banned, community=community).update(
            role=Membership.Role.MODERATOR
        )
        community.banned_keywords = "secret"
        community.save()
        api.force_authenticate(banned)
        assert "banned_keywords" not in api.get(detail_url("py")).data


@pytest.mark.django_db
class TestBannedUserActions:
    def test_cannot_comment(self, api, banned, post):
        api.force_authenticate(banned)
        resp = api.post(comments_url(post.id), {"body": "hi"}, format="json")
        assert resp.status_code == 403

    def test_cannot_vote_on_post_or_comment(self, api, banned, owner, post):
        comment = Comment.objects.create(post=post, author=owner, body="c")
        api.force_authenticate(banned)
        for content_type, object_id in (("post", post.id), ("comment", comment.id)):
            resp = api.post(
                VOTE,
                {"content_type": content_type, "object_id": object_id, "value": 1},
                format="json",
            )
            assert resp.status_code == 403

    def test_cannot_vote_in_poll(self, api, banned, post):
        poll = Poll.objects.create(post=post, closes_at=timezone.now() + timezone.timedelta(days=1))
        option = PollOption.objects.create(poll=poll, text="a")
        api.force_authenticate(banned)
        resp = api.post(poll_vote_url(poll.id), {"option_id": option.id}, format="json")
        assert resp.status_code == 403


@pytest.mark.django_db
class TestClosedContent:
    def test_cannot_comment_on_deleted_post(self, api, owner, post):
        Post.objects.filter(pk=post.pk).update(deleted_at=timezone.now(), deleted_by=owner)
        api.force_authenticate(owner)
        assert api.post(comments_url(post.id), {"body": "hi"}, format="json").status_code == 403

    def test_cannot_vote_on_pending_post(self, api, owner, community):
        pending = Post.objects.create(
            author=owner, community=community, title="p", is_approved=False
        )
        voter = User.objects.create_user(
            username="voter", email="v@x.com", password="StrongPass123!"
        )
        api.force_authenticate(voter)
        resp = api.post(
            VOTE, {"content_type": "post", "object_id": pending.id, "value": 1}, format="json"
        )
        assert resp.status_code == 400


@pytest.mark.django_db
class TestBannedEditsAndReplies:
    def test_banned_author_cannot_edit_own_post(self, api, banned, community):
        own = Post.objects.create(author=banned, community=community, title="t")
        api.force_authenticate(banned)
        url = reverse("api_v1:posts:post-detail", args=[own.pk])
        assert api.patch(url, {"title": "new"}, format="json").status_code == 403

    def test_banned_author_cannot_edit_own_comment(self, api, banned, post):
        own = Comment.objects.create(post=post, author=banned, body="c")
        api.force_authenticate(banned)
        url = reverse("api_v1:comments:comment-detail", args=[own.pk])
        assert api.patch(url, {"body": "new"}, format="json").status_code == 403

    def test_cannot_reply_to_deleted_comment(self, api, owner, post):
        parent = Comment.objects.create(
            post=post, author=owner, body="c", deleted_at=timezone.now()
        )
        api.force_authenticate(owner)
        resp = api.post(comments_url(post.id), {"body": "hi", "parent": parent.id}, format="json")
        assert resp.status_code == 400

    def test_cannot_reparent_comment_on_edit(self, api, owner, post):
        other = Comment.objects.create(post=post, author=owner, body="o")
        own = Comment.objects.create(post=post, author=owner, body="c")
        api.force_authenticate(owner)
        url = reverse("api_v1:comments:comment-detail", args=[own.pk])
        resp = api.patch(url, {"parent": other.id}, format="json")
        assert resp.status_code == 400

    def test_cannot_vote_in_poll_on_unapproved_post(self, api, owner, community):
        pending = Post.objects.create(
            author=owner, community=community, title="p", is_approved=False
        )
        poll = Poll.objects.create(
            post=pending, closes_at=timezone.now() + timezone.timedelta(days=1)
        )
        option = PollOption.objects.create(poll=poll, text="a")
        voter = User.objects.create_user(
            username="voter", email="v@x.com", password="StrongPass123!"
        )
        api.force_authenticate(voter)
        resp = api.post(poll_vote_url(poll.id), {"option_id": option.id}, format="json")
        assert resp.status_code == 404

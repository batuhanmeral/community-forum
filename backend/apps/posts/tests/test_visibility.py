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


def post_url(pk):
    return reverse("api_v1:posts:post-detail", args=[pk])


def comment_url(pk):
    return reverse("api_v1:comments:comment-detail", args=[pk])


def user_comments_url(username):
    return reverse("api_v1:comments:user-comments", args=[username])


def _user(name):
    return User.objects.create_user(username=name, email=f"{name}@x.com", password="StrongPass123!")


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def owner(db):
    return _user("owner")


@pytest.fixture
def author(db):
    return _user("author")


@pytest.fixture
def community(owner):
    return Community.objects.create(slug="py", name="Py", creator=owner)


@pytest.fixture
def pending(author, community):
    return Post.objects.create(author=author, community=community, title="held", is_approved=False)


@pytest.mark.django_db
class TestPendingPosts:
    def test_hidden_from_anonymous_and_strangers(self, api, pending):
        assert api.get(post_url(pending.id)).status_code == 404
        api.force_authenticate(_user("stranger"))
        assert api.get(post_url(pending.id)).status_code == 404

    def test_visible_to_author_with_flag(self, api, author, pending):
        api.force_authenticate(author)
        resp = api.get(post_url(pending.id))
        assert resp.status_code == 200
        assert resp.data["is_approved"] is False

    def test_visible_to_moderator(self, api, owner, pending):
        api.force_authenticate(owner)
        assert api.get(post_url(pending.id)).status_code == 200

    def test_banned_moderator_cannot_see(self, api, community, pending):
        mod = _user("mod")
        Membership.objects.create(
            user=mod, community=community, role=Membership.Role.MODERATOR, is_banned=True
        )
        api.force_authenticate(mod)
        assert api.get(post_url(pending.id)).status_code == 404

    def test_is_approved_not_writable(self, api, author, pending):
        api.force_authenticate(author)
        api.patch(post_url(pending.id), {"is_approved": True}, format="json")
        pending.refresh_from_db()
        assert pending.is_approved is False


@pytest.mark.django_db
class TestDeletedPosts:
    def test_link_and_poll_masked(self, api, author, community):
        link = Post.objects.create(
            author=author, community=community, kind="link", title="l", url="https://x.com/a"
        )
        poll_post = Post.objects.create(author=author, community=community, kind="poll", title="p")
        poll = Poll.objects.create(
            post=poll_post, closes_at=timezone.now() + timezone.timedelta(days=1)
        )
        PollOption.objects.create(poll=poll, text="a")
        Post.objects.filter(pk__in=[link.pk, poll_post.pk]).update(
            deleted_at=timezone.now(), deleted_by=author
        )
        assert api.get(post_url(link.id)).data["url"] == ""
        assert api.get(post_url(poll_post.id)).data["poll"] is None

    def test_author_cannot_edit_deleted_post(self, api, author, community):
        post = Post.objects.create(
            author=author, community=community, title="t", deleted_at=timezone.now()
        )
        api.force_authenticate(author)
        assert api.patch(post_url(post.id), {"title": "new"}, format="json").status_code == 400


@pytest.mark.django_db
class TestDeletedComments:
    def test_author_cannot_edit_deleted_comment(self, api, author, community):
        post = Post.objects.create(author=author, community=community, title="t")
        comment = Comment.objects.create(
            post=post, author=author, body="x", deleted_at=timezone.now(), deleted_by=author
        )
        api.force_authenticate(author)
        assert api.patch(comment_url(comment.id), {"body": "y"}, format="json").status_code == 400

    def test_profile_comments_skip_hidden_posts(self, api, author, pending, community):
        Comment.objects.create(post=pending, author=author, body="on held post")
        visible = Post.objects.create(author=author, community=community, title="ok")
        Comment.objects.create(post=visible, author=author, body="on visible post")
        bodies = [c["body"] for c in api.get(user_comments_url("author")).data["results"]]
        assert bodies == ["on visible post"]


@pytest.mark.django_db
class TestPendingPoll:
    def test_poll_of_pending_post_hidden(self, api, author, community):
        post = Post.objects.create(
            author=author, community=community, kind="poll", title="p", is_approved=False
        )
        poll = Poll.objects.create(post=post, closes_at=timezone.now() + timezone.timedelta(days=1))
        PollOption.objects.create(poll=poll, text="a")
        url = reverse("api_v1:polls:poll-detail", args=[poll.id])
        assert api.get(url).status_code == 404
        api.force_authenticate(author)
        assert api.get(url).status_code == 200


@pytest.mark.django_db
class TestFixRound:
    def test_poll_of_deleted_post_404(self, api, author, community):
        post = Post.objects.create(author=author, community=community, kind="poll", title="p")
        poll = Poll.objects.create(post=post, closes_at=timezone.now() + timezone.timedelta(days=1))
        Post.objects.filter(pk=post.pk).update(deleted_at=timezone.now(), deleted_by=author)
        assert api.get(reverse("api_v1:polls:poll-detail", args=[poll.id])).status_code == 404

    def test_comments_of_pending_post_hidden(self, api, author, pending):
        url = reverse("api_v1:post-comments:post-comments", args=[pending.id])
        assert api.get(url).status_code == 404
        api.force_authenticate(author)
        assert api.get(url).status_code == 200

    def test_cannot_save_pending_post_same_as_missing(self, api, pending):
        api.force_authenticate(_user("stranger"))
        saved = reverse("api_v1:saves:saved-list")
        hidden = api.post(saved, {"content_type": "post", "object_id": pending.id}, format="json")
        missing = api.post(saved, {"content_type": "post", "object_id": 99999}, format="json")
        assert hidden.status_code == missing.status_code == 400
        assert hidden.data == missing.data

    def test_cannot_save_comment_on_pending_post(self, api, author, pending):
        comment = Comment.objects.create(post=pending, author=author, body="c")
        api.force_authenticate(_user("stranger"))
        resp = api.post(
            reverse("api_v1:saves:saved-list"),
            {"content_type": "comment", "object_id": comment.id},
            format="json",
        )
        assert resp.status_code == 400

    def test_saved_target_masked_after_post_held(self, api, author, community):
        post = Post.objects.create(author=author, community=community, title="t")
        stranger = _user("stranger")
        saved = reverse("api_v1:saves:saved-list")
        for u in (stranger, author):
            api.force_authenticate(u)
            assert (
                api.post(
                    saved, {"content_type": "post", "object_id": post.id}, format="json"
                ).status_code
                == 201
            )
        Post.objects.filter(pk=post.pk).update(is_approved=False)
        api.force_authenticate(stranger)
        items = api.get(saved).data["results"]
        assert len(items) == 1 and items[0]["target"] is None
        api.force_authenticate(author)
        assert api.get(saved).data["results"][0]["target"]["id"] == post.id


@pytest.mark.django_db
class TestCommentOnPendingPost:
    def test_comment_detail_hidden(self, api, author, pending):
        comment = Comment.objects.create(post=pending, author=author, body="c")
        assert api.get(comment_url(comment.id)).status_code == 404
        api.force_authenticate(author)
        assert api.get(comment_url(comment.id)).status_code == 200

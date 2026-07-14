import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.comments.models import Comment
from apps.communities.models import Community, Membership
from apps.posts.models import Post

User = get_user_model()


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="alice", email="a@x.com", password="x")


@pytest.fixture
def bob(db):
    return User.objects.create_user(username="bob", email="b@x.com", password="x")


@pytest.fixture
def community(alice):
    return Community.objects.create(slug="py", name="Python", creator=alice)


@pytest.fixture
def mod(bob, community):
    Membership.objects.create(user=bob, community=community, role=Membership.Role.MODERATOR)
    return bob


def post_url(pk):
    return reverse("api_v1:posts:post-detail", args=[pk])


def comment_url(pk):
    return reverse("api_v1:comments:comment-detail", args=[pk])


@pytest.mark.django_db
class TestPostSoftDelete:
    def test_author_delete_marks_as_deleted(self, api, alice, community):
        post = Post.objects.create(author=alice, community=community, kind="text", title="t", body="x")
        api.force_authenticate(alice)
        resp = api.delete(post_url(post.id))
        assert resp.status_code == 204
        post.refresh_from_db()
        assert post.deleted_at is not None
        assert post.deleted_by == alice

    def test_author_deleted_shows_deleted_marker(self, api, alice, community):
        post = Post.objects.create(author=alice, community=community, kind="text", title="t", body="secret")
        api.force_authenticate(alice)
        api.delete(post_url(post.id))
        resp = api.get(post_url(post.id))
        assert resp.data["is_deleted"] is True
        assert resp.data["body"] == "[deleted]"
        assert resp.data["author"] is None
        assert "secret" not in resp.data["body_html"]

    def test_mod_deleted_shows_removed_marker(self, api, alice, mod, community):
        post = Post.objects.create(author=alice, community=community, kind="text", title="t", body="hi")
        api.force_authenticate(mod)
        api.delete(post_url(post.id))
        resp = api.get(post_url(post.id))
        assert resp.data["is_deleted"] is True
        assert resp.data["body"] == "[removed]"

    def test_double_delete_idempotent(self, api, alice, community):
        post = Post.objects.create(author=alice, community=community, kind="text", title="t")
        api.force_authenticate(alice)
        api.delete(post_url(post.id))
        first = Post.objects.get(pk=post.pk).deleted_at
        api.delete(post_url(post.id))
        second = Post.objects.get(pk=post.pk).deleted_at
        assert first == second


@pytest.mark.django_db
class TestCommentSoftDelete:
    def test_author_delete_marks(self, api, alice, community):
        post = Post.objects.create(author=alice, community=community, kind="text", title="t")
        comment = Comment.objects.create(post=post, author=alice, body="hi")
        api.force_authenticate(alice)
        api.delete(comment_url(comment.id))
        comment.refresh_from_db()
        assert comment.deleted_at is not None
        assert comment.body == "hi"  # raw stored

    def test_deleted_comment_in_list_shows_marker(self, api, alice, community):
        post = Post.objects.create(author=alice, community=community, kind="text", title="t")
        comment = Comment.objects.create(post=post, author=alice, body="secret")
        api.force_authenticate(alice)
        api.delete(comment_url(comment.id))
        url = reverse("api_v1:post-comments:post-comments", args=[post.id])
        row = api.get(url).data["results"][0]
        assert row["is_deleted"] is True
        assert row["body"] == "[deleted]"
        assert row["author"] is None
        assert row["author_username"] is None

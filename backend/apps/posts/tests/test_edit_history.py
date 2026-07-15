import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.comments.models import Comment, CommentRevision
from apps.communities.models import Community, Membership
from apps.posts.models import Post, PostRevision

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
def post(alice, community):
    return Post.objects.create(author=alice, community=community, kind="text", title="t", body="v1")


@pytest.fixture
def comment(alice, post):
    return Comment.objects.create(post=post, author=alice, body="v1")


@pytest.mark.django_db
class TestPostEdit:
    def test_edit_creates_revision_and_sets_edited_at(self, api, alice, post):
        api.force_authenticate(alice)
        resp = api.patch(reverse("api_v1:posts:post-detail", args=[post.id]), {"body": "v2"}, format="json")
        assert resp.status_code == 200
        post.refresh_from_db()
        assert post.body == "v2"
        assert post.edited_at is not None
        assert resp.data["edited_at"] is not None
        revs = PostRevision.objects.filter(post=post)
        assert revs.count() == 1
        assert revs.first().body == "v1"

    def test_no_change_does_not_create_revision(self, api, alice, post):
        api.force_authenticate(alice)
        api.patch(reverse("api_v1:posts:post-detail", args=[post.id]), {"body": "v1"}, format="json")
        assert PostRevision.objects.count() == 0
        post.refresh_from_db()
        assert post.edited_at is None

    def test_revision_list_requires_author_or_mod(self, api, alice, bob, post):
        PostRevision.objects.create(post=post, title=post.title, body="old", edited_by=alice)
        api.force_authenticate(bob)
        resp = api.get(reverse("api_v1:posts:post-revisions", args=[post.id]))
        assert resp.status_code == 403

    def test_author_can_list_revisions(self, api, alice, post):
        PostRevision.objects.create(post=post, title=post.title, body="old", edited_by=alice)
        api.force_authenticate(alice)
        resp = api.get(reverse("api_v1:posts:post-revisions", args=[post.id]))
        assert resp.status_code == 200
        assert resp.data["count"] == 1


@pytest.mark.django_db
class TestCommentEdit:
    def test_edit_creates_revision(self, api, alice, comment):
        api.force_authenticate(alice)
        resp = api.patch(reverse("api_v1:comments:comment-detail", args=[comment.id]), {"body": "v2"}, format="json")
        assert resp.status_code == 200
        comment.refresh_from_db()
        assert comment.body == "v2"
        assert comment.edited_at is not None
        assert CommentRevision.objects.filter(comment=comment).count() == 1

    def test_mod_can_view_history(self, api, alice, bob, community, comment):
        Membership.objects.create(user=bob, community=community, role=Membership.Role.MODERATOR)
        CommentRevision.objects.create(comment=comment, body="old", edited_by=alice)
        api.force_authenticate(bob)
        resp = api.get(reverse("api_v1:comments:comment-revisions", args=[comment.id]))
        assert resp.status_code == 200
        assert resp.data["count"] == 1

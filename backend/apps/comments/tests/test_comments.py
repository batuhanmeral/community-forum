import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.comments.models import Comment
from apps.communities.models import Community
from apps.notifications.models import Notification
from apps.posts.models import Post

User = get_user_model()


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="alice", email="a@x.com", password="StrongPass123!")


@pytest.fixture
def bob(db):
    return User.objects.create_user(username="bob", email="b@x.com", password="StrongPass123!")


@pytest.fixture
def carol(db):
    return User.objects.create_user(username="carol", email="c@x.com", password="StrongPass123!")


@pytest.fixture
def community(alice):
    return Community.objects.create(slug="python", name="Python", creator=alice)


@pytest.fixture
def post(alice, community):
    return Post.objects.create(author=alice, community=community, kind="text", title="t")


def list_url(post_id):
    return reverse("api_v1:post-comments:post-comments", args=[post_id])


def detail_url(comment_id):
    return reverse("api_v1:comments:comment-detail", args=[comment_id])


@pytest.mark.django_db
class TestCommentCRUD:
    def test_anonymous_can_list(self, api, post):
        Comment.objects.create(post=post, author=post.author, body="hi")
        resp = api.get(list_url(post.id))
        assert resp.status_code == 200
        assert resp.data["count"] == 1

    def test_anonymous_cannot_create(self, api, post):
        resp = api.post(list_url(post.id), {"body": "hi"}, format="json")
        assert resp.status_code == 401

    def test_authed_creates_top_level_comment(self, api, post, bob):
        api.force_authenticate(bob)
        resp = api.post(list_url(post.id), {"body": "nice"}, format="json")
        assert resp.status_code == 201
        assert resp.data["author"] == bob.id
        assert resp.data["parent"] is None

    def test_reply_threads_under_parent(self, api, post, bob):
        parent = Comment.objects.create(post=post, author=post.author, body="parent")
        api.force_authenticate(bob)
        resp = api.post(list_url(post.id), {"body": "child", "parent": parent.id}, format="json")
        assert resp.status_code == 201
        assert resp.data["parent"] == parent.id

    def test_parent_must_belong_to_post(self, api, post, bob, alice, community):
        other_post = Post.objects.create(author=alice, community=community, kind="text", title="o")
        foreign_parent = Comment.objects.create(post=other_post, author=alice, body="x")
        api.force_authenticate(bob)
        resp = api.post(
            list_url(post.id), {"body": "x", "parent": foreign_parent.id}, format="json"
        )
        assert resp.status_code == 400

    def test_empty_body_rejected(self, api, post, bob):
        api.force_authenticate(bob)
        resp = api.post(list_url(post.id), {"body": "   "}, format="json")
        assert resp.status_code == 400

    def test_author_can_edit_and_delete(self, api, post, bob):
        comment = Comment.objects.create(post=post, author=bob, body="old")
        api.force_authenticate(bob)
        resp = api.patch(detail_url(comment.id), {"body": "new"}, format="json")
        assert resp.status_code == 200
        comment.refresh_from_db()
        assert comment.body == "new"
        resp = api.delete(detail_url(comment.id))
        assert resp.status_code == 204

    def test_non_author_cannot_edit(self, api, post, alice, bob):
        comment = Comment.objects.create(post=post, author=alice, body="hi")
        api.force_authenticate(bob)
        resp = api.patch(detail_url(comment.id), {"body": "hijack"}, format="json")
        assert resp.status_code == 403


@pytest.mark.django_db
class TestCommentNotifications:
    def test_top_level_notifies_post_author(self, api, post, bob):
        api.force_authenticate(bob)
        api.post(list_url(post.id), {"body": "hey"}, format="json")
        n = Notification.objects.get(recipient=post.author)
        assert n.verb == "comment"
        assert n.actor == bob

    def test_reply_notifies_parent_author(self, api, post, bob, carol):
        parent = Comment.objects.create(post=post, author=bob, body="p")
        api.force_authenticate(carol)
        api.post(list_url(post.id), {"body": "r", "parent": parent.id}, format="json")
        assert Notification.objects.filter(recipient=bob, verb="reply").exists()

    def test_no_self_notification(self, api, post):
        # post author commenting on own post → no notification
        api.force_authenticate(post.author)
        api.post(list_url(post.id), {"body": "self"}, format="json")
        assert not Notification.objects.filter(recipient=post.author, verb="comment").exists()

    def test_mention_creates_notification(self, api, post, bob, carol):
        api.force_authenticate(bob)
        api.post(list_url(post.id), {"body": "ping @carol here"}, format="json")
        assert Notification.objects.filter(recipient=carol, verb="mention").exists()

    def test_mention_excludes_self(self, api, post, bob):
        api.force_authenticate(bob)
        api.post(list_url(post.id), {"body": "I am @bob"}, format="json")
        assert not Notification.objects.filter(recipient=bob, verb="mention").exists()

    def test_post_create_mentions_notify(self, api, community, bob, carol):
        api.force_authenticate(bob)
        url = reverse("api_v1:community-posts:community-posts", args=[community.slug])
        # bob must join the community to post
        from apps.communities.models import Membership

        Membership.objects.create(user=bob, community=community)
        api.post(url, {"title": "t", "kind": "text", "body": "hi @carol"}, format="json")
        assert Notification.objects.filter(recipient=carol, verb="mention").exists()

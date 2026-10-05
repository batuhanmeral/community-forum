import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.comments.lib.mentions import MAX_MENTIONS
from apps.comments.models import Comment
from apps.communities.models import Community
from apps.notifications.models import Notification
from apps.posts.models import Post

User = get_user_model()


def _user(name, **extra):
    return User.objects.create_user(username=name, email=f"{name}@x.com", password="x", **extra)


def comments_url(pk):
    return reverse("api_v1:post-comments:post-comments", args=[pk])


def comment_url(pk):
    return reverse("api_v1:comments:comment-detail", args=[pk])


def post_url(pk):
    return reverse("api_v1:posts:post-detail", args=[pk])


@pytest.fixture
def alice(db):
    return _user("alice")


@pytest.fixture
def post(alice):
    community = Community.objects.create(slug="py", name="Py", creator=alice)
    return Post.objects.create(author=alice, community=community, title="t")


@pytest.fixture
def api(alice):
    client = APIClient()
    client.force_authenticate(alice)
    return client


def _mentions_for(user):
    return Notification.objects.filter(recipient=user, verb="mention").count()


@pytest.mark.django_db
class TestMentionRules:
    def test_editing_does_not_renotify_existing_mentions(self, api, post):
        bob = _user("bob")
        comment_id = api.post(comments_url(post.id), {"body": "hi @bob"}, format="json").data["id"]
        api.patch(comment_url(comment_id), {"body": "hi @bob, edited"}, format="json")
        assert _mentions_for(bob) == 1

    def test_editing_notifies_newly_added_mentions(self, api, post):
        carol = _user("carol")
        comment = Comment.objects.create(post=post, author=post.author, body="hi")
        api.patch(comment_url(comment.id), {"body": "hi @carol"}, format="json")
        assert _mentions_for(carol) == 1

    def test_mentions_are_capped(self, api, post):
        users = [_user(f"user{i}") for i in range(MAX_MENTIONS + 2)]
        body = " ".join(f"@{u.username}" for u in users)
        api.post(comments_url(post.id), {"body": body}, format="json")
        assert Notification.objects.filter(verb="mention").count() == MAX_MENTIONS

    def test_deactivated_users_are_not_notified(self, api, post):
        ghost = _user("ghost", is_active=False)
        api.post(comments_url(post.id), {"body": "@ghost"}, format="json")
        assert _mentions_for(ghost) == 0

    def test_post_edit_notifies_new_mentions(self, api, post):
        dave = _user("dave")
        api.patch(post_url(post.id), {"body": "cc @dave"}, format="json")
        assert _mentions_for(dave) == 1

    def test_remove_and_readd_mention_does_not_renotify_comment(self, api, post):
        bob = _user("bob")
        comment_id = api.post(comments_url(post.id), {"body": "hi @bob"}, format="json").data["id"]
        api.patch(comment_url(comment_id), {"body": "hi"}, format="json")
        api.patch(comment_url(comment_id), {"body": "hi @bob again"}, format="json")
        assert _mentions_for(bob) == 1

    def test_remove_and_readd_mention_does_not_renotify_post(self, api, post):
        dave = _user("dave")
        api.patch(post_url(post.id), {"body": "cc @dave"}, format="json")
        api.patch(post_url(post.id), {"body": "cc"}, format="json")
        api.patch(post_url(post.id), {"body": "cc @dave again"}, format="json")
        assert _mentions_for(dave) == 1

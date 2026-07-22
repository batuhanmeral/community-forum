import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from rest_framework.test import APIClient

from apps.comments.models import Comment
from apps.communities.models import Community
from apps.posts.models import Post
from apps.votes.models import Vote

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
def post(alice):
    c = Community.objects.create(slug="c", name="C", creator=alice)
    return Post.objects.create(author=alice, community=c, kind="text", title="t")


def _vote(user, comment, value):
    Vote.objects.create(
        user=user,
        content_type=ContentType.objects.get_for_model(Comment),
        object_id=comment.id,
        value=value,
    )


def list_url(post_id):
    return reverse("api_v1:post-comments:post-comments", args=[post_id])


@pytest.mark.django_db
class TestCommentSort:
    def test_top_orders_by_score(self, api, alice, bob, post):
        low = Comment.objects.create(post=post, author=alice, body="low")
        high = Comment.objects.create(post=post, author=alice, body="high")
        _vote(bob, high, 1)
        ids = [c["id"] for c in api.get(list_url(post.id), {"sort": "top"}).data["results"]]
        assert ids.index(high.id) < ids.index(low.id)

    def test_new_orders_by_created_at_desc(self, api, alice, post):
        first = Comment.objects.create(post=post, author=alice, body="first")
        second = Comment.objects.create(post=post, author=alice, body="second")
        ids = [c["id"] for c in api.get(list_url(post.id), {"sort": "new"}).data["results"]]
        assert ids[0] == second.id and ids[-1] == first.id

    def test_old_orders_by_created_at_asc(self, api, alice, post):
        first = Comment.objects.create(post=post, author=alice, body="first")
        second = Comment.objects.create(post=post, author=alice, body="second")
        ids = [c["id"] for c in api.get(list_url(post.id), {"sort": "old"}).data["results"]]
        assert ids[0] == first.id and ids[-1] == second.id

    def test_controversial_prefers_balanced_high_engagement(self, api, alice, bob, post):
        # high-score comment: clearly top
        winner = Comment.objects.create(post=post, author=alice, body="w")
        _vote(bob, winner, 1)
        # balanced comment: 1 up, 1 down → abs score 0, engagement 2
        carol = User.objects.create_user(username="carol", email="c@x.com", password="x")
        balanced = Comment.objects.create(post=post, author=alice, body="b")
        _vote(bob, balanced, 1)
        _vote(carol, balanced, -1)
        ids = [c["id"] for c in api.get(list_url(post.id), {"sort": "controversial"}).data["results"]]
        assert ids.index(balanced.id) < ids.index(winner.id)

    def test_best_default(self, api, alice, bob, post):
        Comment.objects.create(post=post, author=alice, body="a")
        b = Comment.objects.create(post=post, author=alice, body="b")
        _vote(bob, b, 1)
        resp = api.get(list_url(post.id))  # no sort param → best
        ids = [c["id"] for c in resp.data["results"]]
        assert ids[0] == b.id

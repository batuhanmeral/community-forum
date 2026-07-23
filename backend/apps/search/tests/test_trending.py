from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.comments.models import Comment
from apps.communities.models import Community
from apps.posts.models import Post
from apps.votes.models import Vote

User = get_user_model()
COMMUNITIES = reverse("api_v1:search:trending-communities")
POSTS = reverse("api_v1:search:trending-posts")


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="alice", email="a@x.com", password="x")


@pytest.fixture
def bob(db):
    return User.objects.create_user(username="bob", email="b@x.com", password="x")


def _old(obj, days=2):
    """Push created_at into the past for objects in the queryset."""
    obj.__class__.objects.filter(pk=obj.pk).update(created_at=timezone.now() - timedelta(days=days))


@pytest.mark.django_db
class TestTrendingCommunities:
    def test_orders_by_recent_activity(self, api, alice):
        hot = Community.objects.create(slug="hot", name="Hot", creator=alice)
        cold = Community.objects.create(slug="cold", name="Cold", creator=alice)
        # Hot: 2 recent posts; Cold: 1 old post
        for _ in range(2):
            Post.objects.create(author=alice, community=hot, kind="text", title="t")
        old_post = Post.objects.create(author=alice, community=cold, kind="text", title="o")
        _old(old_post, days=5)
        resp = api.get(COMMUNITIES)
        assert resp.status_code == 200
        slugs = [c["slug"] for c in resp.data["results"]]
        assert slugs.index("hot") < slugs.index("cold")

    def test_recent_comments_count(self, api, alice, bob):
        c = Community.objects.create(slug="c", name="C", creator=alice)
        post = Post.objects.create(author=alice, community=c, kind="text", title="t")
        for _ in range(3):
            Comment.objects.create(post=post, author=bob, body="hi")
        other = Community.objects.create(slug="other", name="Other", creator=alice)
        Post.objects.create(author=alice, community=other, kind="text", title="t")
        resp = api.get(COMMUNITIES)
        # Both have 1 recent post — c has more comments so it wins
        slugs = [c["slug"] for c in resp.data["results"]]
        assert slugs.index("c") < slugs.index("other")


@pytest.mark.django_db
class TestTrendingPosts:
    def _vote(self, user, post, value):
        Vote.objects.create(
            user=user,
            content_type=ContentType.objects.get_for_model(Post),
            object_id=post.id,
            value=value,
        )

    def test_orders_by_score(self, api, alice, bob):
        community = Community.objects.create(slug="c", name="C", creator=alice)
        low = Post.objects.create(author=alice, community=community, kind="text", title="low")
        high = Post.objects.create(author=alice, community=community, kind="text", title="high")
        self._vote(bob, high, 1)
        resp = api.get(POSTS)
        ids = [p["id"] for p in resp.data["results"]]
        assert ids.index(high.id) < ids.index(low.id)

    def test_excludes_old_posts(self, api, alice):
        community = Community.objects.create(slug="c", name="C", creator=alice)
        fresh = Post.objects.create(author=alice, community=community, kind="text", title="new")
        stale = Post.objects.create(author=alice, community=community, kind="text", title="old")
        _old(stale, days=2)
        ids = [p["id"] for p in api.get(POSTS).data["results"]]
        assert fresh.id in ids
        assert stale.id not in ids

    def test_excludes_nsfw(self, api, alice):
        community = Community.objects.create(slug="c", name="C", creator=alice)
        safe = Post.objects.create(author=alice, community=community, kind="text", title="safe")
        Post.objects.create(
            author=alice, community=community, kind="text", title="nsfw", is_nsfw=True
        )
        ids = [p["id"] for p in api.get(POSTS).data["results"]]
        assert safe.id in ids
        assert len(ids) == 1


@pytest.mark.django_db
class TestCache:
    def test_results_cached(self, api, alice):
        community = Community.objects.create(slug="c", name="C", creator=alice)
        Post.objects.create(author=alice, community=community, kind="text", title="first")
        first = api.get(POSTS).data["count"]
        # Add a new post; cached response should still show 1
        Post.objects.create(author=alice, community=community, kind="text", title="second")
        cached = api.get(POSTS).data["count"]
        assert cached == first

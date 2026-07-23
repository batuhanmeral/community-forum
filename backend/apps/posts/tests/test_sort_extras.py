from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

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
def community(alice):
    return Community.objects.create(slug="c", name="C", creator=alice)


def _vote(user, post, value):
    Vote.objects.create(
        user=user,
        content_type=ContentType.objects.get_for_model(Post),
        object_id=post.id,
        value=value,
    )


def list_url(slug):
    return reverse("api_v1:community-posts:community-posts", args=[slug])


@pytest.mark.django_db
class TestTimeTop:
    def test_top_t_week_excludes_older(self, api, alice, bob, community):
        fresh = Post.objects.create(author=alice, community=community, kind="text", title="fresh")
        stale = Post.objects.create(author=alice, community=community, kind="text", title="stale")
        _vote(bob, stale, 1)
        Post.objects.filter(pk=stale.pk).update(created_at=timezone.now() - timedelta(days=40))
        ids = [
            p["id"] for p in api.get(list_url("c"), {"sort": "top", "t": "week"}).data["results"]
        ]
        assert fresh.id in ids
        assert stale.id not in ids

    def test_top_t_all_includes_old(self, api, alice, community):
        stale = Post.objects.create(author=alice, community=community, kind="text", title="stale")
        Post.objects.filter(pk=stale.pk).update(created_at=timezone.now() - timedelta(days=400))
        ids = [p["id"] for p in api.get(list_url("c"), {"sort": "top", "t": "all"}).data["results"]]
        assert stale.id in ids


@pytest.mark.django_db
class TestHotSort:
    def test_hot_returns_results(self, api, alice, bob, community):
        a = Post.objects.create(author=alice, community=community, kind="text", title="a")
        b = Post.objects.create(author=alice, community=community, kind="text", title="b")
        _vote(bob, b, 1)
        resp = api.get(list_url("c"), {"sort": "hot"})
        assert resp.status_code == 200
        ids = [p["id"] for p in resp.data["results"]]
        # b has positive score → should beat a
        assert ids.index(b.id) < ids.index(a.id)

    def test_hot_prefers_newer_when_scores_equal(self, api, alice, community):
        old_post = Post.objects.create(author=alice, community=community, kind="text", title="old")
        Post.objects.filter(pk=old_post.pk).update(created_at=timezone.now() - timedelta(days=30))
        new_post = Post.objects.create(author=alice, community=community, kind="text", title="new")
        ids = [p["id"] for p in api.get(list_url("c"), {"sort": "hot"}).data["results"]]
        assert ids.index(new_post.id) < ids.index(old_post.id)

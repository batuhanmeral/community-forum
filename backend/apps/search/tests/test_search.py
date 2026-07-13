import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.communities.models import Community
from apps.posts.models import Post

User = get_user_model()
SEARCH = reverse("api_v1:search:search")


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def alice(db):
    return User.objects.create_user(
        username="alice", email="a@x.com", password="x", bio="loves python"
    )


@pytest.fixture
def community(alice):
    return Community.objects.create(
        slug="python", name="Python", creator=alice, description="Python language"
    )


@pytest.mark.django_db
class TestSearchPosts:
    def test_q_required(self, api):
        resp = api.get(SEARCH)
        assert resp.status_code == 400
        assert "q" in resp.data

    def test_invalid_type_rejected(self, api):
        resp = api.get(SEARCH, {"q": "x", "type": "banana"})
        assert resp.status_code == 400

    def test_post_title_match(self, api, alice, community):
        match = Post.objects.create(
            author=alice, community=community, kind="text", title="Pythonic generators"
        )
        Post.objects.create(
            author=alice, community=community, kind="text", title="Rust ownership"
        )
        resp = api.get(SEARCH, {"q": "pythonic", "type": "post"})
        assert resp.status_code == 200
        ids = [p["id"] for p in resp.data["results"]]
        assert match.id in ids
        assert len(ids) == 1

    def test_post_body_match(self, api, alice, community):
        match = Post.objects.create(
            author=alice,
            community=community,
            kind="text",
            title="x",
            body="Discussion about asyncio internals",
        )
        resp = api.get(SEARCH, {"q": "asyncio", "type": "post"})
        ids = [p["id"] for p in resp.data["results"]]
        assert match.id in ids

    def test_title_and_body_both_searched(self, api, alice, community):
        body_match = Post.objects.create(
            author=alice, community=community, kind="text", title="Rust", body="zigzag mentions"
        )
        title_match = Post.objects.create(
            author=alice, community=community, kind="text", title="Zigzag fundamentals"
        )
        resp = api.get(SEARCH, {"q": "zigzag", "type": "post"})
        ids = {p["id"] for p in resp.data["results"]}
        assert {body_match.id, title_match.id} <= ids


@pytest.mark.django_db
class TestSearchCommunities:
    def test_name_match(self, api, community):
        Community.objects.create(slug="rust", name="Rust", creator=community.creator)
        resp = api.get(SEARCH, {"q": "python", "type": "community"})
        slugs = [c["slug"] for c in resp.data["results"]]
        assert "python" in slugs
        assert "rust" not in slugs


@pytest.mark.django_db
class TestSearchUsers:
    def test_username_match(self, api, alice):
        User.objects.create_user(username="bob", email="b@x.com", password="x")
        resp = api.get(SEARCH, {"q": "alice", "type": "user"})
        names = [u["username"] for u in resp.data["results"]]
        assert "alice" in names
        assert "bob" not in names

    def test_bio_match(self, api, alice):
        resp = api.get(SEARCH, {"q": "python", "type": "user"})
        names = [u["username"] for u in resp.data["results"]]
        assert "alice" in names

    def test_user_results_hide_email(self, api, alice):
        resp = api.get(SEARCH, {"q": "alice", "type": "user"})
        assert "email" not in resp.data["results"][0]

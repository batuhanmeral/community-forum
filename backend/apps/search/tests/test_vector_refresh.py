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
    return User.objects.create_user(username="alice", email="a@x.com", password="x")


@pytest.fixture
def post(alice):
    community = Community.objects.create(slug="python", name="Python", creator=alice)
    return Post.objects.create(author=alice, community=community, kind="text", title="hello")


def test_last_login_save_does_not_touch_search_vector(alice, django_assert_num_queries):
    with django_assert_num_queries(1):
        alice.save(update_fields=["last_login"])


def test_post_edited_at_save_does_not_touch_search_vector(post, django_assert_num_queries):
    with django_assert_num_queries(1):
        post.save(update_fields=["edited_at"])


def test_bio_update_fields_still_refreshes_vector(api, alice):
    alice.bio = "zeppelin"
    alice.save(update_fields=["bio"])
    resp = api.get(SEARCH, {"q": "zeppelin", "type": "user"})
    assert [u["username"] for u in resp.data["results"]] == ["alice"]


def test_full_save_still_refreshes_vector(api, alice):
    alice.bio = "zeppelin"
    alice.save()
    resp = api.get(SEARCH, {"q": "zeppelin", "type": "user"})
    assert [u["username"] for u in resp.data["results"]] == ["alice"]

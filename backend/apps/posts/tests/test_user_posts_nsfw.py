import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.communities.models import Community
from apps.posts.models import Post

User = get_user_model()
USER_POSTS = reverse("api_v1:posts:user-posts", args=["author"])


@pytest.fixture
def author(db):
    return User.objects.create_user(username="author", email="a@x.com", password="x")


@pytest.fixture
def community(author):
    return Community.objects.create(slug="safe", name="Safe", creator=author)


@pytest.fixture
def posts(author, community):
    safe = Post.objects.create(author=author, community=community, title="safe")
    nsfw = Post.objects.create(author=author, community=community, title="nsfw", is_nsfw=True)
    return safe, nsfw


def _ids(resp):
    return {p["id"] for p in resp.data["results"]}


@pytest.mark.django_db
class TestUserPostsNsfw:
    def test_profile_hides_nsfw_posts_from_other_viewers(self, posts):
        safe, _ = posts
        assert _ids(APIClient().get(USER_POSTS)) == {safe.id}

    def test_profile_hides_posts_from_nsfw_communities(self, author):
        adult = Community.objects.create(slug="adult", name="Adult", creator=author, is_nsfw=True)
        Post.objects.create(author=author, community=adult, title="legacy")
        assert _ids(APIClient().get(USER_POSTS)) == set()

    def test_profile_shows_nsfw_to_opted_in_viewer(self, posts):
        viewer = User.objects.create_user(
            username="viewer", email="v@x.com", password="x", show_nsfw=True
        )
        client = APIClient()
        client.force_authenticate(viewer)
        assert _ids(client.get(USER_POSTS)) == {p.id for p in posts}

    def test_profile_shows_authors_own_nsfw_posts(self, author, posts):
        client = APIClient()
        client.force_authenticate(author)
        assert _ids(client.get(USER_POSTS)) == {p.id for p in posts}

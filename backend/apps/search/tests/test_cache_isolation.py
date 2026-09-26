import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.communities.models import Community
from apps.posts.models import Post
from apps.social.models import Follow
from apps.votes.models import Vote

User = get_user_model()

TRENDING_COMMUNITIES = reverse("api_v1:search:trending-communities")
TRENDING_POSTS = reverse("api_v1:search:trending-posts")
LEADERBOARD = reverse("api_v1:users:users-leaderboard")


def _bearer_client(user) -> APIClient:
    # A real Authorization header (not force_authenticate) so the cache can vary on it.
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="alice", email="a@x.com", password="StrongPass123!")


@pytest.fixture
def bob(db):
    return User.objects.create_user(username="bob", email="b@x.com", password="StrongPass123!")


@pytest.fixture
def post(alice):
    community = Community.objects.create(
        slug="python", name="Python", creator=alice, banned_keywords="secret"
    )
    return Post.objects.create(author=alice, community=community, title="hello")


@pytest.mark.django_db
class TestCachedEndpointsNotServedAnonymousCachedCopy:
    def test_trending_communities_not_served_anonymous_cached_copy(self, alice, post):
        # Warm cache with anonymous request (no Authorization header, so no Vary: Authorization).
        APIClient().get(TRENDING_COMMUNITIES)

        # Now authenticate as admin (creator) and request again.
        admin_view = _bearer_client(alice).get(TRENDING_COMMUNITIES).json()["results"][0]
        # Admin should see mod-only fields, not the anonymous cached response.
        assert admin_view["banned_keywords"] == "secret"
        assert admin_view["is_member"] is True
        assert admin_view["my_role"] == "admin"

    def test_trending_posts_not_served_anonymous_cached_copy(self, bob, post):
        Vote.objects.create(
            user=bob,
            content_type=ContentType.objects.get_for_model(Post),
            object_id=post.id,
            value=1,
        )
        # Warm cache with anonymous request.
        APIClient().get(TRENDING_POSTS)

        # Bob should see his vote, not the anonymous cached response (user_vote=None).
        bob_view = _bearer_client(bob).get(TRENDING_POSTS).json()["results"][0]
        assert bob_view["user_vote"] == 1

    def test_leaderboard_not_served_anonymous_cached_copy(self, alice, bob):
        Follow.objects.create(follower=bob, followed=alice)
        # Warm cache with anonymous request.
        APIClient().get(LEADERBOARD)

        # Bob should see is_following=True, not the anonymous cached response (is_following=False).
        bob_view = {u["username"]: u for u in _bearer_client(bob).get(LEADERBOARD).json()}
        assert bob_view["alice"]["is_following"] is True

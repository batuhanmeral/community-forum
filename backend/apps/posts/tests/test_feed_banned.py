import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.communities.models import Community, Membership
from apps.posts.models import Post

User = get_user_model()
FEED = reverse("api_v1:feed:feed")


@pytest.fixture
def viewer_api(db):
    owner = User.objects.create_user(username="owner", email="o@x.com", password="x")
    viewer = User.objects.create_user(username="viewer", email="v@x.com", password="x")
    for slug, banned in (("joined", False), ("banned", True)):
        community = Community.objects.create(slug=slug, name=slug, creator=owner)
        Membership.objects.create(user=viewer, community=community, is_banned=banned)
        Post.objects.create(author=owner, community=community, title=slug, body="x")
    client = APIClient()
    client.force_authenticate(viewer)
    return client


def test_banned_community_posts_leave_the_personal_feed(viewer_api):
    slugs = {p["community"] for p in viewer_api.get(FEED).data["results"]}
    assert slugs == {"joined"}


def test_scope_all_still_lists_banned_community_posts(viewer_api):
    slugs = {p["community"] for p in viewer_api.get(FEED, {"scope": "all"}).data["results"]}
    assert "banned" in slugs

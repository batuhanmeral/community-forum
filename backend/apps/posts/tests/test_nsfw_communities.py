import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APIClient

from apps.communities.models import Community
from apps.posts.models import Post

User = get_user_model()
FEED = reverse("api_v1:feed:feed")
TRENDING = reverse("api_v1:search:trending-posts")


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="alice", email="a@x.com", password="x")


@pytest.fixture
def nsfw_community(alice):
    return Community.objects.create(slug="adult", name="Adult", creator=alice, is_nsfw=True)


@pytest.mark.django_db
class TestNsfwCommunities:
    def test_new_posts_inherit_the_flag(self, alice, nsfw_community):
        client = APIClient()
        client.force_authenticate(alice)
        resp = client.post(
            reverse("api_v1:community-posts:community-posts", args=["adult"]),
            {"kind": "text", "title": "t", "is_nsfw": False},
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["is_nsfw"] is True

    def test_untagged_posts_hidden_from_sfw_feeds(self, alice, nsfw_community):
        Post.objects.create(author=alice, community=nsfw_community, title="legacy")
        assert APIClient().get(FEED, {"scope": "all"}).data["results"] == []
        assert APIClient().get(TRENDING).json()["results"] == []

    def test_og_preview_has_no_image(self, alice, nsfw_community):
        gif = SimpleUploadedFile("x.gif", b"GIF89a", content_type="image/gif")
        post = Post.objects.create(author=alice, community=nsfw_community, title="t", image=gif)
        html = APIClient().get(reverse("og:og-post", args=[post.id])).content.decode()
        assert "og:image" not in html

    def test_trending_communities_hide_nsfw(self, alice, nsfw_community):
        Community.objects.create(slug="safe", name="Safe", creator=alice)
        resp = APIClient().get(reverse("api_v1:search:trending-communities"))
        assert [c["slug"] for c in resp.json()["results"]] == ["safe"]

    def test_author_cannot_unflag_post_in_nsfw_community(self, alice, nsfw_community):
        post = Post.objects.create(author=alice, community=nsfw_community, title="t", is_nsfw=True)
        client = APIClient()
        client.force_authenticate(alice)
        resp = client.patch(
            reverse("api_v1:posts:post-detail", args=[post.id]), {"is_nsfw": False}, format="json"
        )
        assert resp.status_code == 200
        assert resp.data["is_nsfw"] is True
        post.refresh_from_db()
        assert post.is_nsfw is True

    def test_legacy_post_in_nsfw_community_reads_as_nsfw(self, alice, nsfw_community):
        post = Post.objects.create(author=alice, community=nsfw_community, title="legacy")
        assert post.is_nsfw is False
        resp = APIClient().get(reverse("api_v1:posts:post-detail", args=[post.id]))
        assert resp.status_code == 200
        assert resp.data["is_nsfw"] is True

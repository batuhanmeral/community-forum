import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.communities.models import Community
from apps.posts.models import Post

User = get_user_model()


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def alice(db):
    return User.objects.create_user(
        username="alice", email="a@x.com", password="x", bio="hello bio"
    )


@pytest.fixture
def community(alice):
    return Community.objects.create(slug="py", name="Python", creator=alice, description="desc")


@pytest.fixture
def post(alice, community):
    return Post.objects.create(
        author=alice, community=community, kind="text", title="OG <Title>", body="OG body"
    )


@pytest.mark.django_db
class TestOGPages:
    def test_post_og_contains_meta(self, api, post):
        resp = api.get(reverse("og:og-post", args=[post.pk]))
        assert resp.status_code == 200
        html = resp.content.decode()
        assert '<meta property="og:title" content="OG &lt;Title&gt;">' in html
        assert "og:description" in html
        assert f"/posts/{post.pk}" in html

    def test_deleted_post_404(self, api, post, alice):
        post.deleted_at = timezone.now()
        post.deleted_by = alice
        post.save()
        assert api.get(reverse("og:og-post", args=[post.pk])).status_code == 404

    def test_community_og(self, api, community):
        resp = api.get(reverse("og:og-community", args=["py"]))
        assert resp.status_code == 200
        assert "c/py" in resp.content.decode()

    def test_user_og(self, api, alice):
        resp = api.get(reverse("og:og-user", args=["alice"]))
        assert resp.status_code == 200
        assert "hello bio" in resp.content.decode()

    def test_inactive_user_404(self, api, alice):
        alice.is_active = False
        alice.save(update_fields=["is_active"])
        assert api.get(reverse("og:og-user", args=["alice"])).status_code == 404


@pytest.mark.django_db
class TestOGNsfw:
    def test_nsfw_post_og_hides_title_and_body(self, api, alice, community):
        gif = SimpleUploadedFile("x.gif", b"GIF89a", content_type="image/gif")
        post = Post.objects.create(
            author=alice,
            community=community,
            title="Secret title",
            body="Secret body",
            is_nsfw=True,
            image=gif,
        )
        html = api.get(reverse("og:og-post", args=[post.pk])).content.decode()
        assert "NSFW post in c/py" in html
        assert "This post is marked NSFW." in html
        assert "Secret title" not in html
        assert "Secret body" not in html
        assert "og:image" not in html

    def test_nsfw_community_og_hides_avatar_and_description(self, api, alice):
        gif = SimpleUploadedFile("a.gif", b"GIF89a", content_type="image/gif")
        adult = Community.objects.create(
            slug="adult",
            name="Adult Name",
            creator=alice,
            description="Explicit description",
            is_nsfw=True,
            avatar=gif,
        )
        html = api.get(reverse("og:og-community", args=[adult.slug])).content.decode()
        assert "og:image" not in html
        assert "An NSFW community on Nexus" in html
        assert "Explicit description" not in html
        assert "Adult Name" not in html

    def test_safe_post_og_unchanged(self, api, post):
        html = api.get(reverse("og:og-post", args=[post.pk])).content.decode()
        assert "OG &lt;Title&gt;" in html
        assert "OG body" in html

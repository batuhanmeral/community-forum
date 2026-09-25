import pytest
from django.contrib.auth import get_user_model
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

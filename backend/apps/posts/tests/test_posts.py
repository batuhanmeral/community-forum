import io

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from apps.communities.models import Community, Flair, Membership
from apps.posts.models import Post
from apps.votes.models import Vote

User = get_user_model()


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "red").save(buf, format="PNG")
    return buf.getvalue()


def _gif_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "blue").save(buf, format="GIF")
    return buf.getvalue()


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="alice", email="a@x.com", password="StrongPass123!")


@pytest.fixture
def bob(db):
    return User.objects.create_user(username="bob", email="b@x.com", password="StrongPass123!")


@pytest.fixture
def community(alice):
    return Community.objects.create(slug="python", name="Python", creator=alice)


@pytest.fixture
def join(community):
    def _join(user, role=Membership.Role.MEMBER):
        Membership.objects.get_or_create(user=user, community=community, defaults={"role": role})

    return _join


def list_url(slug):
    return reverse("api_v1:community-posts:community-posts", args=[slug])


def detail_url(pk):
    return reverse("api_v1:posts:post-detail", args=[pk])


def sticky_url(pk):
    return reverse("api_v1:posts:post-sticky", args=[pk])


@pytest.mark.django_db
class TestPostCreate:
    def test_anonymous_cannot_create(self, api, community):
        resp = api.post(list_url("python"), {"title": "hi", "kind": "text"}, format="json")
        assert resp.status_code == 401

    def test_non_member_cannot_create(self, api, community, bob):
        api.force_authenticate(bob)
        resp = api.post(list_url("python"), {"title": "hi", "kind": "text"}, format="json")
        assert resp.status_code == 403

    def test_member_creates_text_post(self, api, community, bob, join):
        join(bob)
        api.force_authenticate(bob)
        resp = api.post(
            list_url("python"), {"title": "hi", "kind": "text", "body": "x"}, format="json"
        )
        assert resp.status_code == 201
        assert resp.data["author"] == bob.id
        assert resp.data["community"] == "python"

    def test_link_post_requires_url(self, api, community, alice):
        api.force_authenticate(alice)
        resp = api.post(list_url("python"), {"title": "x", "kind": "link"}, format="json")
        assert resp.status_code == 400
        assert "url" in resp.data

    def test_image_post_requires_image(self, api, community, alice):
        api.force_authenticate(alice)
        resp = api.post(list_url("python"), {"title": "x", "kind": "image"}, format="json")
        assert resp.status_code == 400
        assert "image" in resp.data

    def test_image_post_with_valid_png(self, api, community, alice):
        api.force_authenticate(alice)
        img = SimpleUploadedFile("a.png", _png_bytes(), content_type="image/png")
        resp = api.post(
            list_url("python"),
            {"title": "x", "kind": "image", "image": img},
            format="multipart",
        )
        assert resp.status_code == 201, resp.data

    def test_image_rejects_unsupported_format(self, api, community, alice):
        api.force_authenticate(alice)
        bad = SimpleUploadedFile("a.gif", _gif_bytes(), content_type="image/gif")
        resp = api.post(
            list_url("python"),
            {"title": "x", "kind": "image", "image": bad},
            format="multipart",
        )
        assert resp.status_code == 400

    def test_flair_must_belong_to_community(self, api, community, alice):
        other = Community.objects.create(slug="go", name="Go", creator=alice)
        foreign_flair = Flair.objects.create(community=other, name="news")
        api.force_authenticate(alice)
        resp = api.post(
            list_url("python"),
            {"title": "x", "kind": "text", "flair": foreign_flair.id},
            format="json",
        )
        assert resp.status_code == 400
        assert "flair" in resp.data


@pytest.mark.django_db
class TestPostListSort:
    def _post(self, author, community, title="t", pinned=False):
        return Post.objects.create(
            author=author, community=community, kind="text", title=title, is_pinned=pinned
        )

    def _vote(self, user, post, value):
        Vote.objects.create(
            user=user,
            content_type=ContentType.objects.get_for_model(Post),
            object_id=post.id,
            value=value,
        )

    def test_pinned_always_on_top(self, api, community, alice, bob):
        old_pinned = self._post(alice, community, "old-pinned", pinned=True)
        self._post(alice, community, "newer")
        resp = api.get(list_url("python"))
        assert resp.status_code == 200
        assert resp.data["results"][0]["id"] == old_pinned.id

    def test_top_sort_by_score(self, api, community, alice, bob):
        low = self._post(alice, community, "low")
        high = self._post(alice, community, "high")
        self._vote(bob, high, 1)
        resp = api.get(list_url("python"), {"sort": "top"})
        ids = [p["id"] for p in resp.data["results"]]
        assert ids.index(high.id) < ids.index(low.id)
        assert next(p for p in resp.data["results"] if p["id"] == high.id)["score"] == 1


@pytest.mark.django_db
class TestPostDetail:
    def test_author_can_update(self, api, community, alice):
        post = Post.objects.create(
            author=alice, community=community, kind="text", title="t", body="x"
        )
        api.force_authenticate(alice)
        resp = api.patch(detail_url(post.id), {"body": "y"}, format="json")
        assert resp.status_code == 200
        post.refresh_from_db()
        assert post.body == "y"

    def test_non_author_cannot_update(self, api, community, alice, bob):
        post = Post.objects.create(author=alice, community=community, kind="text", title="t")
        api.force_authenticate(bob)
        resp = api.patch(detail_url(post.id), {"body": "y"}, format="json")
        assert resp.status_code == 403

    def test_author_can_delete(self, api, community, alice):
        post = Post.objects.create(author=alice, community=community, kind="text", title="t")
        api.force_authenticate(alice)
        resp = api.delete(detail_url(post.id))
        assert resp.status_code == 204


@pytest.mark.django_db
class TestSticky:
    def test_non_mod_cannot_sticky(self, api, community, alice, bob, join):
        join(bob)
        post = Post.objects.create(author=bob, community=community, kind="text", title="t")
        api.force_authenticate(bob)
        resp = api.post(sticky_url(post.id))
        assert resp.status_code == 403

    def test_mod_can_sticky_and_unsticky(self, api, community, alice):
        # alice is creator → admin Membership via signal
        post = Post.objects.create(author=alice, community=community, kind="text", title="t")
        api.force_authenticate(alice)
        resp = api.post(sticky_url(post.id))
        assert resp.status_code == 200
        post.refresh_from_db()
        assert post.is_pinned is True
        resp = api.delete(sticky_url(post.id))
        assert resp.status_code == 200
        post.refresh_from_db()
        assert post.is_pinned is False

    def test_sticky_limit_enforced(self, api, community, alice):
        for i in range(2):
            Post.objects.create(
                author=alice, community=community, kind="text", title=f"p{i}", is_pinned=True
            )
        third = Post.objects.create(author=alice, community=community, kind="text", title="p3")
        api.force_authenticate(alice)
        resp = api.post(sticky_url(third.id))
        assert resp.status_code == 400

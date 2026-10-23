import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.communities.models import Community
from apps.posts.models import Post

User = get_user_model()


def sticky_url(pk):
    return reverse("api_v1:posts:post-sticky", args=[pk])


def detail_url(pk):
    return reverse("api_v1:posts:post-detail", args=[pk])


@pytest.fixture
def owner(db):
    return User.objects.create_user(username="owner", email="o@x.com", password="x")


@pytest.fixture
def community(owner):
    return Community.objects.create(slug="py", name="Py", creator=owner)


@pytest.fixture
def api(owner):
    client = APIClient()
    client.force_authenticate(owner)
    return client


@pytest.mark.django_db
class TestStickySlots:
    def test_deleting_a_pinned_post_frees_its_slot(self, api, owner, community):
        a, b, c = (Post.objects.create(author=owner, community=community, title=n) for n in "abc")
        api.post(sticky_url(a.id))
        api.post(sticky_url(b.id))
        api.delete(detail_url(a.id))
        a.refresh_from_db()
        assert a.is_pinned is False
        assert api.post(sticky_url(c.id)).status_code == 200

    def test_removed_or_pending_posts_cannot_be_pinned(self, api, owner, community):
        removed = Post.objects.create(
            author=owner, community=community, title="r", deleted_at=timezone.now()
        )
        pending = Post.objects.create(
            author=owner, community=community, title="p", is_approved=False
        )
        assert api.post(sticky_url(removed.id)).status_code == 400
        assert api.post(sticky_url(pending.id)).status_code == 400

    def test_pin_racing_a_hold_does_not_pin(self, api, owner, community):
        from unittest.mock import patch

        from apps.posts.views import PostStickyView

        post = Post.objects.create(author=owner, community=community, title="t")
        stale = Post.objects.get(pk=post.pk)
        Post.objects.filter(pk=post.pk).update(is_approved=False)
        with patch.object(PostStickyView, "_get_post", return_value=stale):
            resp = api.post(sticky_url(post.id))
        assert resp.status_code == 400
        assert Post.objects.get(pk=post.pk).is_pinned is False

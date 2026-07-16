import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.communities.models import Community, Membership
from apps.posts.models import Post

User = get_user_model()


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="alice", email="a@x.com", password="x")


@pytest.fixture
def bob(db):
    return User.objects.create_user(username="bob", email="b@x.com", password="x")


@pytest.fixture
def carol(db):
    return User.objects.create_user(username="carol", email="c@x.com", password="x")


@pytest.fixture
def gated_community(alice):
    return Community.objects.create(
        slug="gated", name="Gated", creator=alice, requires_approval=True
    )


@pytest.fixture
def open_community(alice):
    return Community.objects.create(slug="open", name="Open", creator=alice)


def list_url(slug):
    return reverse("api_v1:community-posts:community-posts", args=[slug])


def queue_url(slug):
    return reverse("api_v1:community-posts:community-approval-queue", args=[slug])


def approve_url(pk):
    return reverse("api_v1:posts:post-approve", args=[pk])


@pytest.mark.django_db
class TestApprovalQueue:
    def test_post_in_open_community_visible_immediately(self, api, bob, open_community):
        Membership.objects.create(user=bob, community=open_community)
        api.force_authenticate(bob)
        api.post(list_url("open"), {"title": "hi", "kind": "text"}, format="json")
        assert api.get(list_url("open")).data["count"] == 1

    def test_post_in_gated_community_hidden_from_listing(self, api, bob, gated_community):
        Membership.objects.create(user=bob, community=gated_community)
        api.force_authenticate(bob)
        api.post(list_url("gated"), {"title": "hi", "kind": "text"}, format="json")
        # author hidden from public listing
        assert api.get(list_url("gated")).data["count"] == 0
        assert Post.objects.get().is_approved is False

    def test_mod_post_auto_approved_even_in_gated(self, api, alice, gated_community):
        # alice is creator (admin) → bypass approval
        api.force_authenticate(alice)
        api.post(list_url("gated"), {"title": "hi", "kind": "text"}, format="json")
        assert Post.objects.get().is_approved is True

    def test_non_mod_cannot_see_queue(self, api, bob, carol, gated_community):
        Membership.objects.create(user=bob, community=gated_community)
        api.force_authenticate(bob)
        api.post(list_url("gated"), {"title": "hi", "kind": "text"}, format="json")
        api.force_authenticate(carol)
        assert api.get(queue_url("gated")).status_code == 403

    def test_mod_sees_queue(self, api, alice, bob, gated_community):
        Membership.objects.create(user=bob, community=gated_community)
        api.force_authenticate(bob)
        api.post(list_url("gated"), {"title": "hi", "kind": "text"}, format="json")
        api.force_authenticate(alice)
        resp = api.get(queue_url("gated"))
        assert resp.data["count"] == 1

    def test_approve_makes_post_visible(self, api, alice, bob, gated_community):
        Membership.objects.create(user=bob, community=gated_community)
        api.force_authenticate(bob)
        api.post(list_url("gated"), {"title": "hi", "kind": "text"}, format="json")
        pending = Post.objects.get()
        api.force_authenticate(alice)
        api.post(approve_url(pending.id))
        pending.refresh_from_db()
        assert pending.is_approved is True
        assert api.get(list_url("gated")).data["count"] == 1

    def test_reject_soft_deletes(self, api, alice, bob, gated_community):
        Membership.objects.create(user=bob, community=gated_community)
        api.force_authenticate(bob)
        api.post(list_url("gated"), {"title": "hi", "kind": "text"}, format="json")
        pending = Post.objects.get()
        api.force_authenticate(alice)
        api.delete(approve_url(pending.id))
        pending.refresh_from_db()
        assert pending.deleted_at is not None

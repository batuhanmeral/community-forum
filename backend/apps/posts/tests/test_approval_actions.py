from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.communities.models import Community, Membership
from apps.moderation.models import ModAction
from apps.notifications.models import Notification
from apps.posts.models import Post
from apps.posts.views import PostApprovalView

User = get_user_model()


def approve_url(pk):
    return reverse("api_v1:posts:post-approve", args=[pk])


def queue_url(slug):
    return reverse("api_v1:community-posts:community-approval-queue", args=[slug])


@pytest.fixture
def owner(db):
    return User.objects.create_user(username="owner", email="o@x.com", password="x")


@pytest.fixture
def author(db):
    return User.objects.create_user(username="author", email="a@x.com", password="x")


@pytest.fixture
def community(owner, author):
    c = Community.objects.create(slug="gated", name="Gated", creator=owner, requires_approval=True)
    Membership.objects.create(user=author, community=c)
    return c


@pytest.fixture
def api(owner):
    client = APIClient()
    client.force_authenticate(owner)
    return client


def _held(author, community):
    return Post.objects.create(author=author, community=community, title="t", is_approved=False)


def _mod_notifications(user):
    return Notification.objects.filter(recipient=user, verb="mod_action").count()


@pytest.mark.django_db
class TestApprovalActions:
    def test_concurrent_approvals_log_and_notify_once(self, api, author, community):
        post = _held(author, community)
        # Each request gets its own copy read before either writes, as two racing mods would.
        snapshots = [Post.objects.get(pk=post.pk), Post.objects.get(pk=post.pk)]
        with patch.object(PostApprovalView, "_get", side_effect=snapshots):
            assert api.post(approve_url(post.pk)).status_code == 200
            assert api.post(approve_url(post.pk)).status_code == 200
        assert ModAction.objects.filter(action=ModAction.Action.POST_APPROVE).count() == 1
        assert _mod_notifications(author) == 1
        assert Post.objects.get(pk=post.pk).is_approved is True

    def test_concurrent_rejections_log_and_notify_once(self, api, author, community):
        post = _held(author, community)
        snapshots = [Post.objects.get(pk=post.pk), Post.objects.get(pk=post.pk)]
        with patch.object(PostApprovalView, "_get", side_effect=snapshots):
            assert api.delete(approve_url(post.pk)).status_code == 200
            assert api.delete(approve_url(post.pk)).status_code == 200
        assert ModAction.objects.filter(action=ModAction.Action.POST_REJECT).count() == 1
        assert _mod_notifications(author) == 1
        assert Post.objects.get(pk=post.pk).deleted_at is not None

    def test_rejected_post_leaves_the_queue(self, api, author, community):
        post = _held(author, community)
        api.delete(approve_url(post.pk))
        assert api.get(queue_url("gated")).data["count"] == 0

    def test_rejecting_a_pinned_post_unpins_it(self, api, owner, community):
        post = Post.objects.create(author=owner, community=community, title="t", is_pinned=True)
        api.delete(approve_url(post.pk))
        assert Post.objects.get(pk=post.pk).is_pinned is False

    def test_approve_racing_a_reject_does_nothing(self, api, author, community):
        User.objects.create_user(username="carol", email="c@x.com", password="x")
        post = Post.objects.create(
            author=author, community=community, title="t", body="hi @carol", is_approved=False
        )
        stale = Post.objects.get(pk=post.pk)
        api.delete(approve_url(post.pk))
        with patch.object(PostApprovalView, "_get", return_value=stale):
            response = api.post(approve_url(post.pk))
        assert response.status_code == 200
        assert response.data == {"is_approved": False, "deleted": True}
        fresh = Post.objects.get(pk=post.pk)
        assert fresh.is_approved is False
        assert fresh.deleted_at is not None
        assert ModAction.objects.filter(action=ModAction.Action.POST_APPROVE).count() == 0
        assert Notification.objects.filter(verb="mention").count() == 0
        assert _mod_notifications(author) == 1

    def test_approve_after_hard_delete_looks_missing(self, api, author, community):
        post = _held(author, community)
        stale = Post.objects.get(pk=post.pk)
        Post.objects.filter(pk=post.pk).delete()
        with patch.object(PostApprovalView, "_get", return_value=stale):
            resp = api.post(approve_url(post.pk))
        missing = api.post(approve_url(999_999))
        assert resp.status_code == missing.status_code == 404
        assert str(resp.data) == str(missing.data)

    def test_approve_with_matching_snapshot_publishes(self, api, author, community):
        post = _held(author, community)
        resp = api.post(approve_url(post.pk), {"edited_at": None}, format="json")
        assert resp.status_code == 200
        assert Post.objects.get(pk=post.pk).is_approved is True

    def test_approve_with_stale_snapshot_conflicts_and_keeps_post_held(
        self, api, author, community
    ):
        post = _held(author, community)
        seen = api.get(queue_url("gated")).data["results"][0]["edited_at"]
        api.force_authenticate(author)
        api.patch(
            reverse("api_v1:posts:post-detail", args=[post.pk]), {"body": "new"}, format="json"
        )
        api.force_authenticate(community.creator)
        resp = api.post(approve_url(post.pk), {"edited_at": seen}, format="json")
        assert resp.status_code == 409
        assert Post.objects.get(pk=post.pk).is_approved is False
        assert ModAction.objects.filter(action=ModAction.Action.POST_APPROVE).count() == 0
        fresh = api.get(queue_url("gated")).data["results"][0]["edited_at"]
        assert (
            api.post(approve_url(post.pk), {"edited_at": fresh}, format="json").status_code == 200
        )

    def test_approve_rejects_a_malformed_snapshot(self, api, author, community):
        post = _held(author, community)
        assert api.post(approve_url(post.pk), {"edited_at": "x"}, format="json").status_code == 400
        assert Post.objects.get(pk=post.pk).is_approved is False

    def test_unticking_nsfw_on_a_held_post_invalidates_the_snapshot(self, api, author, community):
        post = Post.objects.create(
            author=author, community=community, title="t", is_approved=False, is_nsfw=True
        )
        seen = api.get(queue_url("gated")).data["results"][0]["edited_at"]
        api.force_authenticate(author)
        api.patch(
            reverse("api_v1:posts:post-detail", args=[post.pk]), {"is_nsfw": False}, format="json"
        )
        api.force_authenticate(community.creator)
        assert api.post(approve_url(post.pk), {"edited_at": seen}, format="json").status_code == 409

    def test_approve_with_a_non_object_body_is_not_a_server_error(self, api, author, community):
        post = _held(author, community)
        resp = api.post(approve_url(post.pk), ["edited_at"], format="json")
        assert resp.status_code == 200

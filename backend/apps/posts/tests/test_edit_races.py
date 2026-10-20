from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.communities.models import Community, Membership
from apps.posts.models import Post, PostRevision
from apps.posts.views import PostDetailView

User = get_user_model()


def _user(name):
    return User.objects.create_user(username=name, email=f"{name}@x.com", password="x")


@pytest.fixture
def owner(db):
    return _user("owner")


@pytest.fixture
def author(db):
    return _user("author")


@pytest.fixture
def community(owner, author):
    c = Community.objects.create(slug="races", name="Races", creator=owner)
    Membership.objects.create(user=author, community=c)
    return c


@pytest.fixture
def post(author, community):
    return Post.objects.create(author=author, community=community, title="old", body="old body")


@pytest.fixture
def author_api(author):
    api = APIClient()
    api.force_authenticate(author)
    return api


def _patch_after_moderator(author_api, post, moderator_write, payload):
    """PATCH while the moderator's write lands right after the author's read."""
    real = PostDetailView.get_object

    def racing(self):
        obj = real(self)
        moderator_write()
        return obj

    with patch.object(PostDetailView, "get_object", autospec=True, side_effect=racing):
        return author_api.patch(
            reverse("api_v1:posts:post-detail", args=[post.id]), payload, format="json"
        )


def test_mod_removal_during_author_edit_stands(author_api, post, owner):
    resp = _patch_after_moderator(
        author_api,
        post,
        lambda: Post.objects.filter(pk=post.pk).update(deleted_at=timezone.now(), deleted_by=owner),
        {"body": "edited"},
    )
    post.refresh_from_db()
    assert resp.status_code == 400
    assert post.deleted_at is not None and post.deleted_by_id == owner.id
    assert post.body == "old body"
    assert not PostRevision.objects.filter(post=post).exists()


def test_mod_pin_during_author_edit_stands(author_api, post):
    resp = _patch_after_moderator(
        author_api,
        post,
        lambda: Post.objects.filter(pk=post.pk).update(is_pinned=True),
        {"title": "new title"},
    )
    post.refresh_from_db()
    assert resp.status_code == 200
    assert post.is_pinned is True and post.title == "new title"


def test_mod_approval_during_author_edit_stands(author_api, post):
    Post.objects.filter(pk=post.pk).update(is_approved=False)
    resp = _patch_after_moderator(
        author_api,
        post,
        lambda: Post.objects.filter(pk=post.pk).update(is_approved=True),
        {"title": "new title"},
    )
    post.refresh_from_db()
    assert resp.status_code == 200
    assert post.is_approved is True and post.title == "new title"

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.communities.models import Community, Membership
from apps.moderation.models import ModAction
from apps.notifications.models import Notification
from apps.posts.models import Post

User = get_user_model()


def detail_url(pk):
    return reverse("api_v1:posts:post-detail", args=[pk])


def list_url(slug):
    return reverse("api_v1:community-posts:community-posts", args=[slug])


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
    c = Community.objects.create(
        slug="strict", name="Strict", creator=owner, banned_keywords="spammy"
    )
    Membership.objects.create(user=author, community=c)
    return c


@pytest.fixture
def api():
    return APIClient()


def _edit(api, user, post, **fields):
    api.force_authenticate(user)
    return api.patch(detail_url(post.pk), fields, format="json")


@pytest.mark.django_db
class TestAutoModOnEdit:
    def test_edit_adding_a_keyword_holds_the_post(self, api, author, community):
        post = Post.objects.create(author=author, community=community, title="hello")
        resp = _edit(api, author, post, title="now SPAMMY")
        assert resp.status_code == 200
        assert resp.data["is_approved"] is False
        assert Post.objects.get(pk=post.pk).is_approved is False
        entry = ModAction.objects.get(action=ModAction.Action.AUTOMOD_HOLD)
        assert entry.actor is None
        assert "spammy" in entry.detail
        api.force_authenticate(None)
        assert api.get(list_url("strict")).data["count"] == 0

    def test_edit_keeping_an_approved_keyword_stays_visible(self, api, author, community):
        # A moderator approved this post although it already contained the keyword.
        post = Post.objects.create(author=author, community=community, title="t", body="spammy")
        resp = _edit(api, author, post, title="t (typo fixed)")
        assert resp.status_code == 200
        assert Post.objects.get(pk=post.pk).is_approved is True
        assert not ModAction.objects.filter(action=ModAction.Action.AUTOMOD_HOLD).exists()

    def test_moderator_author_bypasses(self, api, owner, community):
        post = Post.objects.create(author=owner, community=community, title="hello")
        _edit(api, owner, post, title="spammy")
        assert Post.objects.get(pk=post.pk).is_approved is True

    def test_post_held_on_edit_loses_its_pin(self, api, author, community):
        post = Post.objects.create(
            author=author, community=community, title="hello", is_pinned=True
        )
        _edit(api, author, post, body="spammy")
        assert Post.objects.get(pk=post.pk).is_pinned is False

    def test_post_held_on_edit_sends_no_mentions(self, api, author, community):
        _user("carol")
        post = Post.objects.create(author=author, community=community, title="hello")
        _edit(api, author, post, body="spammy @carol")
        assert not Notification.objects.filter(verb="mention").exists()

    def test_clean_edit_stays_approved(self, api, author, community):
        post = Post.objects.create(author=author, community=community, title="hello")
        _edit(api, author, post, title="hello again")
        assert Post.objects.get(pk=post.pk).is_approved is True

    def test_hold_is_written_with_the_edit(self, api, author, community):
        post = Post.objects.create(author=author, community=community, title="hello")
        with patch(
            "apps.posts.views.PostRevision.objects.create", side_effect=RuntimeError("boom")
        ):
            with pytest.raises(RuntimeError):
                _edit(api, author, post, body="spammy")
        assert Post.objects.get(pk=post.pk).is_approved is False

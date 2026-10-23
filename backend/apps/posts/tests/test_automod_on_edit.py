from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
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
        # The edit runs in one transaction, so the keyword and its hold stand or fall together.
        stored = Post.objects.get(pk=post.pk)
        assert (stored.body, stored.is_approved) == ("", True)


@pytest.mark.django_db
class TestAutoModCoverage:
    @pytest.mark.parametrize(
        "payload",
        [
            {"title": "hi", "body": "s.p.a.m.m.y offer"},
            {"title": "hi", "body": "sp&#97;mmy"},
            {"title": "ＳＰＡＭＭＹ"},
            {"title": "hi", "kind": "link", "url": "https://spammy.example"},
            {"title": "hi", "kind": "link", "url": "https://xn--spmmy-hra.example"},
            {"title": "hi", "body": "[click](https://sp&#97;mmy.example)"},
            {"title": "hi", "body": "[click](https://%73pammy.example)"},
        ],
    )
    def test_create_holds_disguised_keywords(self, api, author, community, payload):
        api.force_authenticate(author)
        resp = api.post(list_url(community.slug), payload, format="json")
        assert resp.status_code == 201, resp.data
        assert Post.objects.get(pk=resp.data["id"]).is_approved is False

    def test_create_holds_keyword_in_poll_option(self, api, author, community):
        api.force_authenticate(author)
        closes_at = (timezone.now() + timedelta(days=1)).isoformat()
        resp = api.post(
            list_url(community.slug),
            {
                "title": "vote",
                "kind": "poll",
                "poll_input": {"options": ["fine", "Spammy deal"], "closes_at": closes_at},
            },
            format="json",
        )
        assert resp.status_code == 201, resp.data
        assert Post.objects.get(pk=resp.data["id"]).is_approved is False

    def test_clean_post_stays_visible(self, api, author, community):
        api.force_authenticate(author)
        resp = api.post(
            list_url(community.slug), {"title": "hello", "body": "spa mmy"}, format="json"
        )
        assert Post.objects.get(pk=resp.data["id"]).is_approved is True

    def test_edit_adding_a_disguised_keyword_holds(self, api, author, community):
        post = Post.objects.create(author=author, community=community, title="hello")
        _edit(api, author, post, body="**spam**my")
        post.refresh_from_db()
        assert post.is_approved is False

    def test_edit_changing_url_to_keyword_holds(self, api, author, community):
        post = Post.objects.create(
            author=author,
            community=community,
            title="hello",
            kind=Post.Kind.LINK,
            url="https://ok.example",
        )
        _edit(api, author, post, url="https://spammy.example")
        post.refresh_from_db()
        assert post.is_approved is False

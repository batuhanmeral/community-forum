import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.comments.serializers import COMMENT_BODY_MAX_CHARS
from apps.communities.models import Community
from apps.messaging.models import Conversation
from apps.messaging.serializers import MESSAGE_BODY_MAX_CHARS
from apps.posts.models import Post
from apps.posts.serializers import POST_BODY_MAX_CHARS

User = get_user_model()


def posts_url(slug):
    return reverse("api_v1:community-posts:community-posts", args=[slug])


def post_url(pk):
    return reverse("api_v1:posts:post-detail", args=[pk])


def comments_url(pk):
    return reverse("api_v1:post-comments:post-comments", args=[pk])


def messages_url(pk):
    return reverse("api_v1:messaging:conversation-messages", args=[pk])


def flairs_url(slug):
    return reverse("api_v1:communities:community-flairs", args=[slug])


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="alice", email="a@x.com", password="StrongPass123!")


@pytest.fixture
def community(alice):
    return Community.objects.create(slug="python", name="Python", creator=alice)


@pytest.fixture
def post(alice, community):
    return Post.objects.create(author=alice, community=community, title="t")


@pytest.mark.django_db
class TestPostBody:
    def test_non_string_body_rejected(self, api, alice, community):
        api.force_authenticate(alice)
        resp = api.post(
            posts_url("python"), {"kind": "text", "title": "t", "body": ["x"]}, format="json"
        )
        assert resp.status_code == 400
        assert "body" in resp.data

    def test_body_length_capped(self, api, alice, community):
        api.force_authenticate(alice)
        resp = api.post(
            posts_url("python"),
            {"kind": "text", "title": "t", "body": "x" * (POST_BODY_MAX_CHARS + 1)},
            format="json",
        )
        assert resp.status_code == 400

    def test_leading_whitespace_preserved(self, api, alice, community):
        api.force_authenticate(alice)
        resp = api.post(
            posts_url("python"),
            {"kind": "text", "title": "t", "body": "    indented code"},
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["body"] == "    indented code"

    def test_kind_cannot_change(self, api, alice, post):
        api.force_authenticate(alice)
        resp = api.patch(post_url(post.id), {"kind": "link", "url": "https://x.com"}, format="json")
        assert resp.status_code == 400
        assert "kind" in resp.data

    def test_url_rejected_on_text_post(self, api, alice, post):
        api.force_authenticate(alice)
        resp = api.patch(post_url(post.id), {"url": "https://x.com"}, format="json")
        assert resp.status_code == 400
        assert "url" in resp.data

    def test_blank_url_rejected_on_link_post(self, api, alice, community):
        link = Post.objects.create(
            author=alice, community=community, title="t", kind="link", url="https://x.com"
        )
        api.force_authenticate(alice)
        resp = api.patch(post_url(link.id), {"url": ""}, format="json")
        assert resp.status_code == 400
        assert "url" in resp.data

    def test_title_only_patch_on_link_post_allowed(self, api, alice, community):
        link = Post.objects.create(
            author=alice, community=community, title="t", kind="link", url="https://x.com"
        )
        api.force_authenticate(alice)
        resp = api.patch(post_url(link.id), {"title": "new"}, format="json")
        assert resp.status_code == 200

    def test_poll_input_rejected_on_update(self, api, alice, post):
        api.force_authenticate(alice)
        resp = api.patch(
            post_url(post.id),
            {"poll_input": {"options": ["a", "b"], "closes_at": "2030-01-01T00:00:00Z"}},
            format="json",
        )
        assert resp.status_code == 400
        assert "poll_input" in resp.data


@pytest.mark.django_db
class TestCommentBody:
    def test_non_string_body_rejected(self, api, alice, post):
        api.force_authenticate(alice)
        resp = api.post(comments_url(post.id), {"body": {"x": 1}}, format="json")
        assert resp.status_code == 400

    def test_body_length_capped(self, api, alice, post):
        api.force_authenticate(alice)
        resp = api.post(
            comments_url(post.id), {"body": "x" * (COMMENT_BODY_MAX_CHARS + 1)}, format="json"
        )
        assert resp.status_code == 400


@pytest.mark.django_db
class TestMessageBody:
    def test_body_length_capped(self, api, alice):
        bob = User.objects.create_user(username="bob", email="b@x.com", password="StrongPass123!")
        a, b = sorted((alice, bob), key=lambda u: u.id)
        conv = Conversation.objects.create(participant_a=a, participant_b=b)
        api.force_authenticate(alice)
        resp = api.post(
            messages_url(conv.id), {"body": "x" * (MESSAGE_BODY_MAX_CHARS + 1)}, format="json"
        )
        assert resp.status_code == 400


@pytest.mark.django_db
class TestFlairColor:
    def test_invalid_color_rejected(self, api, alice, community):
        api.force_authenticate(alice)
        resp = api.post(flairs_url("python"), {"name": "news", "color": "red;}"}, format="json")
        assert resp.status_code == 400
        assert "color" in resp.data

    def test_hex_color_accepted(self, api, alice, community):
        api.force_authenticate(alice)
        resp = api.post(flairs_url("python"), {"name": "news", "color": "#12ab9F"}, format="json")
        assert resp.status_code == 201

    def test_color_with_trailing_newline_is_trimmed_not_500(self, api, alice, community):
        api.force_authenticate(alice)
        resp = api.post(flairs_url("python"), {"name": "news", "color": "#aabbcc\n"}, format="json")
        assert resp.status_code == 201
        assert resp.data["color"] == "#aabbcc"

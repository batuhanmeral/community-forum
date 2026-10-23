import io

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from apps.communities.models import Community, Membership
from apps.moderation.models import ModAction
from apps.notifications.models import Notification
from apps.posts.models import Post

User = get_user_model()


def detail(pk):
    return reverse("api_v1:posts:post-detail", args=[pk])


def queue_url(slug):
    return reverse("api_v1:community-posts:community-approval-queue", args=[slug])


def approve_url(pk):
    return reverse("api_v1:posts:post-approve", args=[pk])


def _user(name):
    return User.objects.create_user(username=name, email=f"{name}@x.com", password="x")


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _png() -> SimpleUploadedFile:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "red").save(buf, format="PNG")
    return SimpleUploadedFile("a.png", buf.getvalue(), content_type="image/png")


@pytest.fixture
def owner(db):
    return _user("owner")


@pytest.fixture
def author(db):
    return _user("author")


@pytest.fixture
def bob(db):
    return _user("bob")


@pytest.fixture
def gated(owner, author):
    community = Community.objects.create(
        slug="gated", name="Gated", creator=owner, requires_approval=True
    )
    Membership.objects.create(user=author, community=community)
    return community


@pytest.fixture
def approved_post(gated, author):
    return Post.objects.create(
        author=author, community=gated, title="t", body="b", is_approved=True, is_pinned=True
    )


def _queue_ids(owner, slug):
    return [row["id"] for row in _client(owner).get(queue_url(slug)).data["results"]]


@pytest.mark.django_db
class TestReapprovalOnEdit:
    def test_author_body_edit_goes_back_to_queue(self, author, owner, gated, approved_post):
        resp = _client(author).patch(detail(approved_post.id), {"body": "changed"}, format="json")
        approved_post.refresh_from_db()
        assert resp.status_code == 200
        assert approved_post.is_approved is False and approved_post.is_pinned is False
        entry = ModAction.objects.get(action=ModAction.Action.AUTOMOD_HOLD)
        assert entry.detail == "edited after approval" and entry.actor is None
        assert approved_post.id in _queue_ids(owner, "gated")

    def test_link_url_edit_goes_back_to_queue(self, author, owner, gated):
        post = Post.objects.create(
            author=author,
            community=gated,
            title="t",
            kind=Post.Kind.LINK,
            url="https://a.example.com/",
            is_approved=True,
        )
        resp = _client(author).patch(detail(post.id), {"url": "https://b.example.com/"})
        post.refresh_from_db()
        assert resp.status_code == 200
        assert post.is_approved is False
        assert ModAction.objects.get(action=ModAction.Action.AUTOMOD_HOLD).detail == (
            "edited after approval"
        )
        assert post.id in _queue_ids(owner, "gated")

    def test_image_upload_goes_back_to_queue(self, author, gated):
        post = Post.objects.create(
            author=author, community=gated, title="t", kind=Post.Kind.IMAGE, is_approved=True
        )
        post.image.save("old.png", _png())
        resp = _client(author).patch(detail(post.id), {"image": _png()}, format="multipart")
        post.refresh_from_db()
        assert resp.status_code == 200, resp.data
        assert post.is_approved is False

    def test_clearing_the_image_goes_back_to_queue(self, author, gated):
        post = Post.objects.create(
            author=author,
            community=gated,
            title="t",
            kind=Post.Kind.IMAGE,
            is_approved=True,
            is_pinned=True,
        )
        post.image.save("old.png", _png())
        resp = _client(author).patch(detail(post.id), {"image": None}, format="json")
        post.refresh_from_db()
        assert resp.status_code == 200, resp.data
        assert post.is_approved is False and post.is_pinned is False
        entry = ModAction.objects.get(action=ModAction.Action.AUTOMOD_HOLD)
        assert entry.detail == "edited after approval"

    def test_resending_the_same_values_stays_visible(self, author, approved_post):
        resp = _client(author).patch(
            detail(approved_post.id), {"title": "t", "body": "b"}, format="json"
        )
        approved_post.refresh_from_db()
        assert resp.status_code == 200
        assert approved_post.is_approved is True and approved_post.is_pinned is True
        assert not ModAction.objects.filter(action=ModAction.Action.AUTOMOD_HOLD).exists()

    def test_keyword_detail_wins_over_edited_after_approval(self, author, gated, approved_post):
        gated.banned_keywords = "spammy"
        gated.save()
        _client(author).patch(detail(approved_post.id), {"body": "spammy"}, format="json")
        entry = ModAction.objects.get(action=ModAction.Action.AUTOMOD_HOLD)
        assert entry.detail == "matched keyword on edit: spammy"

    def test_flair_or_nsfw_only_edit_stays_visible(self, author, approved_post):
        resp = _client(author).patch(detail(approved_post.id), {"is_nsfw": True}, format="json")
        approved_post.refresh_from_db()
        assert resp.status_code == 200
        assert approved_post.is_approved is True and approved_post.is_nsfw is True

    def test_flair_only_edit_stays_visible(self, author, gated, approved_post):
        from apps.communities.models import Flair

        flair = Flair.objects.create(community=gated, name="News")
        resp = _client(author).patch(detail(approved_post.id), {"flair": flair.id}, format="json")
        approved_post.refresh_from_db()
        assert resp.status_code == 200, resp.data
        assert approved_post.flair_id == flair.id and approved_post.is_approved is True

    def test_moderator_author_edit_stays_visible(self, owner, gated):
        post = Post.objects.create(
            author=owner, community=gated, title="t", body="b", is_approved=True
        )
        resp = _client(owner).patch(detail(post.id), {"body": "changed"}, format="json")
        post.refresh_from_db()
        assert resp.status_code == 200
        assert post.is_approved is True

    def test_open_community_edit_stays_visible(self, owner, author):
        community = Community.objects.create(slug="open", name="Open", creator=owner)
        Membership.objects.create(user=author, community=community)
        post = Post.objects.create(
            author=author, community=community, title="t", body="b", is_approved=True
        )
        resp = _client(author).patch(detail(post.id), {"body": "changed"}, format="json")
        post.refresh_from_db()
        assert resp.status_code == 200
        assert post.is_approved is True

    def test_held_edit_sends_mentions_only_on_approval(self, author, owner, bob, approved_post):
        _client(author).patch(detail(approved_post.id), {"body": "hi @bob"}, format="json")
        mentions = Notification.objects.filter(recipient=bob, verb="mention")
        assert mentions.count() == 0
        _client(owner).post(approve_url(approved_post.id))
        assert mentions.count() == 1
        assert mentions.get().actor == author

    def test_dropping_nsfw_sends_post_back_to_queue(self, owner, author, gated):
        post = Post.objects.create(
            author=author, community=gated, title="t", is_approved=True, is_nsfw=True
        )
        resp = _client(author).patch(detail(post.id), {"is_nsfw": False}, format="json")
        post.refresh_from_db()
        assert resp.status_code == 200
        assert post.is_approved is False and post.is_nsfw is False
        assert post.id in _queue_ids(owner, "gated")

    def test_url_edit_marks_post_edited(self, author, gated):
        post = Post.objects.create(
            author=author,
            community=gated,
            title="t",
            kind=Post.Kind.LINK,
            url="https://a.example",
            is_approved=False,
        )
        _client(author).patch(detail(post.id), {"url": "https://b.example"}, format="json")
        post.refresh_from_db()
        assert post.edited_at is not None

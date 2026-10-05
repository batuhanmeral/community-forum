import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.communities.models import Community, Membership
from apps.notifications.models import Notification
from apps.posts.models import Post

User = get_user_model()


def _user(name):
    return User.objects.create_user(username=name, email=f"{name}@x.com", password="x")


def list_url(slug):
    return reverse("api_v1:community-posts:community-posts", args=[slug])


def post_url(pk):
    return reverse("api_v1:posts:post-detail", args=[pk])


def approve_url(pk):
    return reverse("api_v1:posts:post-approve", args=[pk])


def _mentions_for(user):
    return Notification.objects.filter(recipient=user, verb="mention").count()


@pytest.fixture
def alice(db):
    return _user("alice")


@pytest.fixture
def bob(db):
    return _user("bob")


@pytest.fixture
def carol(db):
    return _user("carol")


@pytest.fixture
def author(db):
    return _user("author")


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def gated(alice, author):
    community = Community.objects.create(
        slug="gated", name="Gated", creator=alice, requires_approval=True
    )
    Membership.objects.create(user=author, community=community)
    return community


@pytest.fixture
def held_post(gated, author, bob):
    return Post.objects.create(
        author=author, community=gated, title="t", body="hi @bob", is_approved=False
    )


@pytest.mark.django_db
class TestHeldPostMentions:
    def test_create_in_gated_community_does_not_notify(self, gated, author, bob):
        resp = _client(author).post(
            list_url("gated"), {"title": "t", "body": "hi @bob", "kind": "text"}, format="json"
        )
        assert resp.status_code == 201
        assert Post.objects.get().is_approved is False
        assert _mentions_for(bob) == 0

    def test_create_held_by_automod_does_not_notify(self, alice, author, bob):
        community = Community.objects.create(
            slug="mod", name="Mod", creator=alice, banned_keywords="spam"
        )
        Membership.objects.create(user=author, community=community)
        resp = _client(author).post(
            list_url("mod"), {"title": "spam", "body": "hi @bob", "kind": "text"}, format="json"
        )
        assert resp.status_code == 201
        assert Post.objects.get().is_approved is False
        assert _mentions_for(bob) == 0

    def test_editing_held_post_does_not_notify(self, held_post, author, carol):
        _client(author).patch(post_url(held_post.id), {"body": "hi @carol"}, format="json")
        assert _mentions_for(carol) == 0

    def test_approval_sends_mentions_with_author_as_actor(self, held_post, alice, author, bob):
        _client(alice).post(approve_url(held_post.id))
        notes = Notification.objects.filter(recipient=bob, verb="mention")
        assert notes.count() == 1
        assert notes.get().actor == author

    def test_approving_twice_does_not_resend(self, held_post, alice, bob):
        client = _client(alice)
        client.post(approve_url(held_post.id))
        client.post(approve_url(held_post.id))
        assert _mentions_for(bob) == 1

    def test_approving_deleted_post_does_not_notify(self, held_post, alice, bob):
        Post.objects.filter(pk=held_post.pk).update(deleted_at=timezone.now())
        _client(alice).post(approve_url(held_post.id))
        assert _mentions_for(bob) == 0

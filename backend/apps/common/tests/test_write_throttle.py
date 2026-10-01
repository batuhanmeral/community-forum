import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.communities.models import Community
from apps.messaging.models import Conversation
from apps.posts.models import Post

User = get_user_model()


def comments_url(pk):
    return reverse("api_v1:post-comments:post-comments", args=[pk])


def posts_url(slug):
    return reverse("api_v1:community-posts:community-posts", args=[slug])


def messages_url(pk):
    return reverse("api_v1:messaging:conversation-messages", args=[pk])


def follow_url(username):
    return reverse("api_v1:social:user-follow", args=[username])


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def tight_write(monkeypatch):
    monkeypatch.setattr(
        ScopedRateThrottle,
        "THROTTLE_RATES",
        {"auth": "100/min", "write": "2/min", "vote": "2/min"},
    )


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="alice", email="a@x.com", password="StrongPass123!")


@pytest.fixture
def bob(db):
    return User.objects.create_user(username="bob", email="b@x.com", password="StrongPass123!")


@pytest.fixture
def post(alice):
    community = Community.objects.create(slug="py", name="Py", creator=alice)
    return Post.objects.create(author=alice, community=community, title="t")


@pytest.mark.django_db
class TestWriteThrottle:
    def test_reads_are_not_counted_as_writes(self, api, alice, post, tight_write):
        api.force_authenticate(alice)
        statuses = [api.get(comments_url(post.id)).status_code for _ in range(4)]
        statuses += [api.get(posts_url("py")).status_code for _ in range(4)]
        assert set(statuses) == {200}

    def test_comment_writes_throttled(self, api, alice, post, tight_write):
        api.force_authenticate(alice)
        statuses = [
            api.post(comments_url(post.id), {"body": f"c{i}"}, format="json").status_code
            for i in range(3)
        ]
        assert statuses == [201, 201, 429]

    def test_direct_messages_throttled(self, api, alice, bob, tight_write):
        a, b = sorted((alice, bob), key=lambda u: u.id)
        conv = Conversation.objects.create(participant_a=a, participant_b=b)
        api.force_authenticate(alice)
        statuses = [
            api.post(messages_url(conv.id), {"body": "hi"}, format="json").status_code
            for _ in range(3)
        ]
        assert statuses[-1] == 429

    def test_follow_toggling_throttled(self, api, alice, bob, tight_write):
        api.force_authenticate(alice)
        statuses = [
            api.post(follow_url("bob")).status_code,
            api.delete(follow_url("bob")).status_code,
            api.post(follow_url("bob")).status_code,
        ]
        assert statuses[-1] == 429

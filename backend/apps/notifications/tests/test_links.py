import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.comments.models import Comment
from apps.communities.models import Community
from apps.messaging.models import Conversation, Message
from apps.notifications.models import Notification
from apps.notifications.services import notify
from apps.posts.models import Post

User = get_user_model()
LIST = reverse("api_v1:notifications:notification-list")


def _user(name):
    return User.objects.create_user(username=name, email=f"{name}@x.com", password="x")


@pytest.fixture
def alice(db):
    return _user("alice")


@pytest.fixture
def bob(db):
    return _user("bob")


@pytest.fixture
def post(alice):
    community = Community.objects.create(slug="py", name="Py", creator=alice)
    return Post.objects.create(author=alice, community=community, title="t")


def _links(user):
    client = APIClient()
    client.force_authenticate(user)
    return [n["link"] for n in client.get(LIST).data["results"]]


@pytest.mark.django_db
class TestNotificationLinks:
    def test_comment_links_to_anchor_in_post(self, alice, bob, post):
        comment = Comment.objects.create(post=post, author=bob, body="hi")
        notify(alice, actor=bob, verb="comment", target=comment)
        assert _links(alice) == [f"/posts/{post.id}#comment-{comment.id}"]

    def test_dm_links_to_conversation(self, alice, bob):
        a, b = sorted((alice, bob), key=lambda u: u.id)
        conv = Conversation.objects.create(participant_a=a, participant_b=b)
        message = Message.objects.create(conversation=conv, sender=bob, body="hey")
        notify(alice, actor=bob, verb="dm", target=message)
        assert _links(alice) == [f"/messages/{conv.id}"]

    def test_follow_links_to_profile(self, alice, bob):
        notify(alice, actor=bob, verb="follow", target=bob)
        assert _links(alice) == ["/u/bob"]

    def test_community_target_links_to_community(self, alice, bob, post):
        notify(bob, actor=alice, verb="mod_action", target=post.community)
        assert _links(bob) == ["/c/py"]

    def test_post_target_links_to_post(self, alice, bob, post):
        notify(alice, actor=bob, verb="mention", target=post)
        assert _links(alice) == [f"/posts/{post.id}"]

    def test_missing_target_has_no_link(self, alice, bob, post):
        comment = Comment.objects.create(post=post, author=bob, body="hi")
        notify(alice, actor=bob, verb="comment", target=comment)
        Comment.objects.filter(pk=comment.pk).delete()
        assert _links(alice) == [None]
        assert Notification.objects.count() == 1

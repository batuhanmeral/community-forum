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


def _comment_link_case(alice, bob, post):
    comment = Comment.objects.create(post=post, author=bob, body="hi")
    return alice, bob, "comment", comment, f"/posts/{post.id}#comment-{comment.id}"


def _message_link_case(alice, bob, _post):
    a, b = sorted((alice, bob), key=lambda u: u.id)
    conv = Conversation.objects.create(participant_a=a, participant_b=b)
    message = Message.objects.create(conversation=conv, sender=bob, body="hey")
    return alice, bob, "dm", message, f"/messages/{conv.id}"


@pytest.mark.django_db
class TestNotificationLinks:
    @pytest.mark.parametrize(
        "build_case",
        [
            pytest.param(_comment_link_case, id="comment-anchor"),
            pytest.param(_message_link_case, id="message-conversation"),
            pytest.param(
                lambda alice, bob, post: (alice, bob, "follow", bob, "/u/bob"), id="user-profile"
            ),
            pytest.param(
                lambda alice, bob, post: (bob, alice, "mod_action", post.community, "/c/py"),
                id="community",
            ),
            pytest.param(
                lambda alice, bob, post: (alice, bob, "mention", post, f"/posts/{post.id}"),
                id="post",
            ),
        ],
    )
    def test_link_by_target_type(self, alice, bob, post, build_case):
        recipient, actor, verb, target, expected_link = build_case(alice, bob, post)
        notify(recipient, actor=actor, verb=verb, target=target)
        assert _links(recipient) == [expected_link]

    def test_missing_target_has_no_link(self, alice, bob, post):
        comment = Comment.objects.create(post=post, author=bob, body="hi")
        notify(alice, actor=bob, verb="comment", target=comment)
        Comment.objects.filter(pk=comment.pk).delete()
        assert _links(alice) == [None]
        assert Notification.objects.count() == 1

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from rest_framework.test import APIClient

from apps.comments.models import Comment
from apps.communities.models import Community
from apps.messaging.models import Conversation, Message
from apps.notifications.models import Notification
from apps.posts.models import Post

User = get_user_model()


def _user(name):
    return User.objects.create_user(username=name, email=f"{name}@x.com", password="x")


@pytest.mark.django_db
def test_ten_notifications_with_mixed_targets_within_six_queries(django_assert_max_num_queries):
    me = _user("me")
    community = Community.objects.create(slug="py", name="Python", creator=me)
    targets = []
    for i in range(3):
        actor = _user(f"a{i}")
        post = Post.objects.create(author=me, community=community, kind="text", title=f"p{i}")
        comment = Comment.objects.create(post=post, author=actor, body="c")
        a, b = sorted((me, actor), key=lambda u: u.id)
        conv = Conversation.objects.create(participant_a=a, participant_b=b)
        message = Message.objects.create(conversation=conv, sender=actor, body="hi")
        targets += [(actor, post), (actor, comment), (actor, message)]
    targets.append((_user("follower"), me))
    for actor, target in targets:
        Notification.objects.create(
            recipient=me,
            actor=actor,
            verb="comment",
            target_ct=ContentType.objects.get_for_model(type(target)),
            target_id=target.pk,
        )
    client = APIClient()
    client.force_authenticate(me)
    with django_assert_max_num_queries(6):
        resp = client.get(reverse("api_v1:notifications:notification-list"))
    assert len(resp.data["results"]) == 10
    assert {r["target_type"] for r in resp.data["results"]} == {
        "post",
        "comment",
        "message",
        "user",
    }

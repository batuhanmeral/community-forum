import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.comments.models import Comment
from apps.communities.models import Community, Membership
from apps.notifications.models import Notification
from apps.notifications.services import notify
from apps.posts.models import Post

User = get_user_model()
LIST = reverse("api_v1:notifications:notification-list")
MARK_ALL = reverse("api_v1:notifications:notification-mark-all-read")


def read_url(pk):
    return reverse("api_v1:notifications:notification-read", args=[pk])


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="alice", email="a@x.com", password="x")


@pytest.fixture
def bob(db):
    return User.objects.create_user(username="bob", email="b@x.com", password="x")


@pytest.fixture
def community(alice):
    return Community.objects.create(slug="py", name="Python", creator=alice)


@pytest.fixture
def post(alice, community):
    return Post.objects.create(author=alice, community=community, kind="text", title="t")


@pytest.mark.django_db
class TestNotifyLevel:
    def test_off_suppresses_comment_notification(self, alice, bob, community, post):
        Membership.objects.filter(user=alice, community=community).update(
            notify_level=Membership.NotifyLevel.OFF
        )
        comment = Comment.objects.create(post=post, author=bob, body="hi")
        notify(alice, actor=bob, verb="comment", target=comment, community=community)
        assert not Notification.objects.filter(recipient=alice).exists()

    def test_off_still_allows_mention(self, alice, bob, community, post):
        Membership.objects.filter(user=alice, community=community).update(
            notify_level=Membership.NotifyLevel.OFF
        )
        comment = Comment.objects.create(post=post, author=bob, body="hi @alice")
        notify(alice, actor=bob, verb="mention", target=comment, community=community)
        assert Notification.objects.filter(recipient=alice, verb="mention").exists()

    def test_posts_only_suppresses_comment(self, alice, bob, community, post):
        Membership.objects.filter(user=alice, community=community).update(
            notify_level=Membership.NotifyLevel.POSTS_ONLY
        )
        comment = Comment.objects.create(post=post, author=bob, body="hi")
        notify(alice, actor=bob, verb="comment", target=comment, community=community)
        assert not Notification.objects.filter(recipient=alice).exists()

    def test_all_delivers_comment(self, alice, bob, community, post):
        comment = Comment.objects.create(post=post, author=bob, body="hi")
        notify(alice, actor=bob, verb="comment", target=comment, community=community)
        assert Notification.objects.filter(recipient=alice, verb="comment").exists()


@pytest.mark.django_db
class TestInbox:
    def test_anonymous_rejected(self, api):
        assert api.get(LIST).status_code == 401

    def test_returns_only_my_notifications(self, api, alice, bob):
        Notification.objects.create(recipient=alice, actor=bob, verb="follow")
        Notification.objects.create(recipient=bob, actor=alice, verb="follow")
        api.force_authenticate(alice)
        resp = api.get(LIST)
        assert resp.data["count"] == 1
        assert resp.data["results"][0]["recipient"] == alice.id

    def test_unread_filter(self, api, alice, bob):
        from django.utils import timezone

        Notification.objects.create(
            recipient=alice, actor=bob, verb="follow", read_at=timezone.now()
        )
        Notification.objects.create(recipient=alice, actor=bob, verb="follow")
        api.force_authenticate(alice)
        resp = api.get(LIST, {"unread": "true"})
        assert resp.data["count"] == 1

    def test_target_type_exposed(self, api, alice, bob, post):
        notify(alice, actor=bob, verb="mention", target=post)
        api.force_authenticate(alice)
        row = api.get(LIST).data["results"][0]
        assert row["target_type"] == "post"
        assert row["target_id"] == post.id


@pytest.mark.django_db
class TestMarkRead:
    def test_mark_one(self, api, alice, bob):
        n = Notification.objects.create(recipient=alice, actor=bob, verb="follow")
        api.force_authenticate(alice)
        resp = api.post(read_url(n.id))
        assert resp.status_code == 200
        n.refresh_from_db()
        assert n.read_at is not None

    def test_mark_one_cannot_touch_others(self, api, alice, bob):
        n = Notification.objects.create(recipient=bob, actor=alice, verb="follow")
        api.force_authenticate(alice)
        assert api.post(read_url(n.id)).status_code == 404

    def test_mark_all(self, api, alice, bob):
        for _ in range(3):
            Notification.objects.create(recipient=alice, actor=bob, verb="follow")
        api.force_authenticate(alice)
        resp = api.post(MARK_ALL)
        assert resp.data["marked_read"] == 3
        assert not Notification.objects.filter(recipient=alice, read_at__isnull=True).exists()


@pytest.mark.django_db
class TestModActionTrigger:
    def test_sticky_notifies_post_author(self, api, alice, community):
        post = Post.objects.create(author=alice, community=community, kind="text", title="t")
        # carol is mod (we make her one via admin role)
        carol = User.objects.create_user(username="carol", email="c@x.com", password="x")
        Membership.objects.create(user=carol, community=community, role=Membership.Role.MODERATOR)
        api.force_authenticate(carol)
        url = reverse("api_v1:posts:post-sticky", args=[post.id])
        api.post(url)
        assert Notification.objects.filter(recipient=alice, verb="mod_action").exists()

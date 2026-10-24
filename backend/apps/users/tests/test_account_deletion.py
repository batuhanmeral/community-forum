import json

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.comments.models import Comment
from apps.communities.models import Community, Membership
from apps.notifications.models import Notification
from apps.posts.models import Post
from apps.saves.models import SavedItem
from apps.social.models import Block, Follow
from apps.votes.models import Vote

User = get_user_model()

ME = reverse("api_v1:users:users-me")
EXPORT = reverse("api_v1:users:users-export")
LOGIN = reverse("api_v1:auth:auth-login")
PW = "StrongPass123!x"


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="alice", email="a@x.com", password=PW, bio="hi")


@pytest.fixture
def bob(db):
    return User.objects.create_user(username="bob", email="b@x.com", password=PW)


@pytest.fixture
def world(alice, bob):
    community = Community.objects.create(slug="py", name="Py", creator=alice)
    Membership.objects.get_or_create(user=bob, community=community)
    post = Post.objects.create(author=alice, community=community, title="mine", body="text")
    comment = Comment.objects.create(post=post, author=alice, body="reply")
    Follow.objects.create(follower=alice, followed=bob)
    Follow.objects.create(follower=bob, followed=alice)
    Block.objects.create(blocker=bob, blocked=alice)
    SavedItem.objects.create(user=alice, target=post)
    Vote.objects.create(user=alice, target=post, value=1)
    Notification.objects.create(recipient=alice, actor=bob, verb="follow")
    return {"community": community, "post": post, "comment": comment}


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.mark.django_db
class TestAccountDeletion:
    def test_requires_the_current_password(self, alice):
        resp = _client(alice).delete(ME, {"password": "wrong"}, format="json")
        assert resp.status_code == 400
        assert "password" in resp.data
        alice.refresh_from_db()
        assert alice.is_active and alice.username == "alice"

    def test_erases_personal_data_and_keeps_content(self, alice, bob, world):
        alice.country = "TR"
        alice.save(update_fields=["country"])
        resp = _client(alice).delete(ME, {"password": PW}, format="json")
        assert resp.status_code == 204
        alice.refresh_from_db()
        assert alice.username == f"deleted-{alice.pk}"
        assert (alice.email, alice.bio, alice.country, alice.is_active) == ("", "", "", False)
        assert not alice.has_usable_password()
        assert not Follow.objects.filter(follower=alice).exists()
        assert not Follow.objects.filter(followed=alice).exists()
        assert not Block.objects.filter(blocked=alice).exists()
        assert not SavedItem.objects.filter(user=alice).exists()
        assert not Notification.objects.filter(recipient=alice).exists()
        assert not Membership.objects.filter(user=alice).exists()
        assert Post.objects.filter(pk=world["post"].pk).exists()
        assert Comment.objects.filter(pk=world["comment"].pk).exists()
        assert Vote.objects.filter(user=alice).count() == 1

    def test_deleted_author_shows_as_deleted(self, alice, bob, world):
        _client(alice).delete(ME, {"password": PW}, format="json")
        post_url = reverse("api_v1:posts:post-detail", args=[world["post"].pk])
        assert _client(bob).get(post_url).data["author_username"] is None

    def test_old_credentials_and_tokens_stop_working(self, alice, world):
        login = APIClient().post(LOGIN, {"username": "alice", "password": PW}, format="json")
        access = login.data["access"]
        _client(alice).delete(ME, {"password": PW}, format="json")
        bearer = APIClient()
        bearer.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        assert bearer.get(ME).status_code == 401
        relogin = APIClient().post(LOGIN, {"username": "alice", "password": PW}, format="json")
        assert relogin.status_code == 401

    def test_clears_the_refresh_cookie(self, alice):
        client = APIClient()
        client.post(LOGIN, {"username": "alice", "password": PW}, format="json")
        client.force_authenticate(alice)
        resp = client.delete(ME, {"password": PW}, format="json")
        assert resp.cookies["nexus_refresh"].value == ""

    def test_username_is_free_for_a_new_sign_up(self, alice):
        _client(alice).delete(ME, {"password": PW}, format="json")
        resp = APIClient().post(
            reverse("api_v1:auth:auth-register"),
            {"username": "alice", "email": "a@x.com", "password": PW},
            format="json",
        )
        assert resp.status_code == 201, resp.data


@pytest.mark.django_db
class TestAccountExport:
    def test_requires_auth(self):
        assert APIClient().get(EXPORT).status_code == 401

    def test_downloads_own_data_as_json(self, alice, bob, world):
        resp = _client(alice).get(EXPORT)
        assert resp.status_code == 200
        assert "attachment" in resp["Content-Disposition"]
        data = json.loads(resp.content)
        assert data["profile"]["username"] == "alice"
        assert data["profile"]["email"] == "a@x.com"
        assert data["profile"]["country"] == ""
        assert [p["title"] for p in data["posts"]] == ["mine"]
        assert [c["body"] for c in data["comments"]] == ["reply"]
        assert data["following"] == ["bob"]
        assert data["votes"] == [{"target": "post", "target_id": world["post"].pk, "value": 1}]
        assert data["saved"] == [{"target": "post", "target_id": world["post"].pk}]
        assert data["memberships"][0]["community"] == "py"

    def test_holds_no_one_elses_private_data(self, alice, bob, world):
        data = json.loads(_client(alice).get(EXPORT).content)
        assert "b@x.com" not in json.dumps(data)


@pytest.mark.django_db
class TestDeletedAccountIsNotRegroupable:
    def test_post_and_comment_hide_the_author_id(self, alice, bob, world):
        _client(alice).delete(ME, {"password": PW}, format="json")
        post_url = reverse("api_v1:posts:post-detail", args=[world["post"].pk])
        assert _client(bob).get(post_url).data["author"] is None
        comments_url = reverse("api_v1:post-comments:post-comments", args=[world["post"].pk])
        assert _client(bob).get(comments_url).data["results"][0]["author"] is None

    def test_history_lists_are_gone(self, alice, world):
        _client(alice).delete(ME, {"password": PW}, format="json")
        name = f"deleted-{alice.pk}"
        assert APIClient().get(reverse("api_v1:posts:user-posts", args=[name])).status_code == 404
        assert (
            APIClient().get(reverse("api_v1:comments:user-comments", args=[name])).status_code
            == 404
        )

    def test_cannot_be_followed_afterwards(self, alice, bob):
        _client(alice).delete(ME, {"password": PW}, format="json")
        url = reverse("api_v1:social:user-follow", args=[f"deleted-{alice.pk}"])
        assert _client(bob).post(url).status_code == 404


@pytest.mark.django_db
class TestDeletionHousekeeping:
    def test_created_community_passes_to_the_highest_ranked_member(self, alice, bob, world):
        carol = User.objects.create_user(username="carol", email="c@x.com", password=PW)
        Membership.objects.create(
            user=carol, community=world["community"], role=Membership.Role.MODERATOR
        )
        _client(alice).delete(ME, {"password": PW}, format="json")
        world["community"].refresh_from_db()
        assert world["community"].creator_id == carol.pk
        assert Membership.objects.get(user=carol, community=world["community"]).role == "admin"

    def test_profile_update_cannot_revive_a_deleted_account(self, alice):
        _client(alice).delete(ME, {"password": PW}, format="json")
        alice.refresh_from_db()
        # force_authenticate skips the active check, standing in for a request authenticated earlier.
        resp = _client(alice).patch(ME, {"bio": "back"}, format="json")
        assert resp.status_code == 401
        alice.refresh_from_db()
        assert (alice.is_active, alice.bio) == (False, "")

    def test_avatar_files_are_removed_after_commit(
        self, alice, tmp_path, settings, django_capture_on_commit_callbacks
    ):
        settings.MEDIA_ROOT = tmp_path
        client = _client(alice)
        with django_capture_on_commit_callbacks(execute=True):
            client.patch(ME, {"avatar": _png("one.png")}, format="multipart")
        first = User.objects.get(pk=alice.pk).avatar.name
        with django_capture_on_commit_callbacks(execute=True):
            client.patch(ME, {"avatar": _png("two.png")}, format="multipart")
        second = User.objects.get(pk=alice.pk).avatar.name
        assert not (tmp_path / first).exists()
        assert (tmp_path / second).exists()
        with django_capture_on_commit_callbacks(execute=True):
            client.delete(ME, {"password": PW}, format="json")
        assert not (tmp_path / second).exists()


def _png(name):
    import io

    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "red").save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


@pytest.mark.django_db
def test_messages_cannot_be_sent_to_a_deleted_account(alice, bob):
    from apps.messaging.models import Conversation

    a, b = sorted([alice, bob], key=lambda u: u.pk)
    conv = Conversation.objects.create(participant_a=a, participant_b=b)
    _client(alice).delete(ME, {"password": PW}, format="json")
    url = reverse("api_v1:messaging:conversation-messages", args=[conv.pk])
    assert _client(bob).post(url, {"body": "hi"}, format="json").status_code == 403


@pytest.mark.django_db
def test_stale_profile_update_cannot_restore_an_old_password(alice):
    stale = User.objects.get(pk=alice.pk)
    fresh = User.objects.get(pk=alice.pk)
    fresh.set_password("NewStrongPass456!y")
    fresh.save(update_fields=["password"])
    client = APIClient()
    # The user object authenticated before the password change, as a slow request would hold it.
    client.force_authenticate(stale)
    assert client.patch(ME, {"bio": "later"}, format="json").status_code == 200
    alice.refresh_from_db()
    assert alice.check_password("NewStrongPass456!y")
    assert alice.bio == "later"


@pytest.mark.django_db
def test_no_notifications_reach_a_deleted_account(alice, bob):
    from apps.notifications.services import notify

    _client(alice).delete(ME, {"password": PW}, format="json")
    alice.refresh_from_db()
    assert notify(alice, actor=bob, verb="follow") is None
    assert not Notification.objects.filter(recipient=alice).exists()

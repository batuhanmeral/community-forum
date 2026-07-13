import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from rest_framework.test import APIClient

from apps.comments.models import Comment
from apps.communities.models import Community
from apps.posts.models import Post
from apps.saves.models import SavedItem

User = get_user_model()
SAVED = reverse("api_v1:saves:saved-list")


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


@pytest.fixture
def comment(alice, post):
    return Comment.objects.create(post=post, author=alice, body="hi")


def payload(target):
    return {"content_type": target.__class__.__name__.lower(), "object_id": target.id}


@pytest.mark.django_db
class TestSaveToggle:
    def test_anonymous_rejected(self, api, post):
        assert api.post(SAVED, payload(post), format="json").status_code == 401

    def test_save_creates(self, api, bob, post):
        api.force_authenticate(bob)
        resp = api.post(SAVED, payload(post), format="json")
        assert resp.status_code == 201
        assert resp.data["is_saved"] is True
        assert SavedItem.objects.filter(user=bob).count() == 1

    def test_save_again_toggles_off(self, api, bob, post):
        api.force_authenticate(bob)
        api.post(SAVED, payload(post), format="json")
        resp = api.post(SAVED, payload(post), format="json")
        assert resp.status_code == 200
        assert resp.data["is_saved"] is False
        assert SavedItem.objects.count() == 0

    def test_save_comment(self, api, bob, comment):
        api.force_authenticate(bob)
        resp = api.post(SAVED, payload(comment), format="json")
        assert resp.status_code == 201
        assert SavedItem.objects.get(user=bob).content_type.model == "comment"

    def test_unknown_target_400(self, api, bob):
        api.force_authenticate(bob)
        resp = api.post(SAVED, {"content_type": "post", "object_id": 9999}, format="json")
        assert resp.status_code == 400

    def test_invalid_content_type(self, api, bob):
        api.force_authenticate(bob)
        resp = api.post(SAVED, {"content_type": "community", "object_id": 1}, format="json")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestSaveList:
    def test_lists_only_own(self, api, alice, bob, post, comment):
        SavedItem.objects.create(
            user=alice,
            content_type=ContentType.objects.get_for_model(Post),
            object_id=post.id,
        )
        SavedItem.objects.create(
            user=bob,
            content_type=ContentType.objects.get_for_model(Comment),
            object_id=comment.id,
        )
        api.force_authenticate(alice)
        resp = api.get(SAVED)
        assert resp.data["count"] == 1
        assert resp.data["results"][0]["target_type"] == "post"

    def test_type_filter(self, api, alice, post, comment):
        SavedItem.objects.create(
            user=alice,
            content_type=ContentType.objects.get_for_model(Post),
            object_id=post.id,
        )
        SavedItem.objects.create(
            user=alice,
            content_type=ContentType.objects.get_for_model(Comment),
            object_id=comment.id,
        )
        api.force_authenticate(alice)
        resp = api.get(SAVED, {"type": "comment"})
        assert resp.data["count"] == 1
        assert resp.data["results"][0]["target_type"] == "comment"

    def test_target_payload_embedded(self, api, alice, post):
        SavedItem.objects.create(
            user=alice,
            content_type=ContentType.objects.get_for_model(Post),
            object_id=post.id,
        )
        api.force_authenticate(alice)
        resp = api.get(SAVED)
        row = resp.data["results"][0]
        assert row["target"]["id"] == post.id
        assert row["target"]["title"] == "t"


@pytest.mark.django_db
class TestIsSavedField:
    def test_post_is_saved_for_viewer(self, api, alice, bob, post):
        SavedItem.objects.create(
            user=alice,
            content_type=ContentType.objects.get_for_model(Post),
            object_id=post.id,
        )
        api.force_authenticate(alice)
        url = reverse("api_v1:community-posts:community-posts", args=[post.community.slug])
        resp = api.get(url)
        row = next(p for p in resp.data["results"] if p["id"] == post.id)
        assert row["is_saved"] is True
        # Other user sees False
        api.force_authenticate(bob)
        row = next(p for p in api.get(url).data["results"] if p["id"] == post.id)
        assert row["is_saved"] is False

    def test_post_is_saved_false_for_anonymous(self, api, post):
        url = reverse("api_v1:community-posts:community-posts", args=[post.community.slug])
        row = next(p for p in api.get(url).data["results"] if p["id"] == post.id)
        assert row["is_saved"] is False

    def test_comment_is_saved(self, api, alice, comment):
        SavedItem.objects.create(
            user=alice,
            content_type=ContentType.objects.get_for_model(Comment),
            object_id=comment.id,
        )
        api.force_authenticate(alice)
        url = reverse("api_v1:post-comments:post-comments", args=[comment.post_id])
        row = api.get(url).data["results"][0]
        assert row["is_saved"] is True

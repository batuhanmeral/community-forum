import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.urls import reverse
from rest_framework.test import APIClient

from apps.comments.models import Comment
from apps.communities.models import Community
from apps.posts.models import Post
from apps.votes.models import Vote

User = get_user_model()
VOTE_URL = reverse("api_v1:votes:vote")


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
    return Community.objects.create(slug="python", name="Python", creator=alice)


@pytest.fixture
def post(alice, community):
    return Post.objects.create(author=alice, community=community, kind="text", title="t")


@pytest.fixture
def comment(alice, post):
    return Comment.objects.create(post=post, author=alice, body="hi")


def _post_payload(target, value):
    return {
        "content_type": target.__class__.__name__.lower(),
        "object_id": target.id,
        "value": value,
    }


@pytest.mark.django_db
class TestVoteEndpoint:
    def test_anonymous_rejected(self, api, post):
        resp = api.post(VOTE_URL, _post_payload(post, 1), format="json")
        assert resp.status_code == 401

    def test_upvote_creates(self, api, post, bob):
        api.force_authenticate(bob)
        resp = api.post(VOTE_URL, _post_payload(post, 1), format="json")
        assert resp.status_code == 201
        assert resp.data["user_vote"] == 1
        assert Vote.objects.count() == 1

    def test_same_value_toggles_delete(self, api, post, bob):
        api.force_authenticate(bob)
        api.post(VOTE_URL, _post_payload(post, 1), format="json")
        resp = api.post(VOTE_URL, _post_payload(post, 1), format="json")
        assert resp.status_code == 200
        assert resp.data["user_vote"] is None
        assert Vote.objects.count() == 0

    def test_opposite_value_updates(self, api, post, bob):
        api.force_authenticate(bob)
        api.post(VOTE_URL, _post_payload(post, 1), format="json")
        resp = api.post(VOTE_URL, _post_payload(post, -1), format="json")
        assert resp.status_code == 200
        assert resp.data["user_vote"] == -1
        assert Vote.objects.count() == 1

    def test_unknown_target_rejected(self, api, bob):
        api.force_authenticate(bob)
        resp = api.post(
            VOTE_URL,
            {"content_type": "post", "object_id": 9999, "value": 1},
            format="json",
        )
        assert resp.status_code == 400

    def test_invalid_content_type_rejected(self, api, bob, post):
        api.force_authenticate(bob)
        resp = api.post(
            VOTE_URL,
            {"content_type": "community", "object_id": post.id, "value": 1},
            format="json",
        )
        assert resp.status_code == 400

    def test_invalid_value_rejected(self, api, bob, post):
        api.force_authenticate(bob)
        resp = api.post(VOTE_URL, _post_payload(post, 0), format="json")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestKarmaSignal:
    def test_post_upvote_increments_post_karma(self, api, post, alice, bob):
        api.force_authenticate(bob)
        api.post(VOTE_URL, _post_payload(post, 1), format="json")
        alice.refresh_from_db()
        assert alice.post_karma == 1
        assert alice.comment_karma == 0

    def test_comment_upvote_increments_comment_karma(self, api, comment, alice, bob):
        api.force_authenticate(bob)
        api.post(VOTE_URL, _post_payload(comment, 1), format="json")
        alice.refresh_from_db()
        assert alice.comment_karma == 1

    def test_flip_vote_applies_delta_of_two(self, api, post, alice, bob):
        api.force_authenticate(bob)
        api.post(VOTE_URL, _post_payload(post, 1), format="json")
        api.post(VOTE_URL, _post_payload(post, -1), format="json")
        alice.refresh_from_db()
        assert alice.post_karma == -1

    def test_toggle_off_reverts(self, api, post, alice, bob):
        api.force_authenticate(bob)
        api.post(VOTE_URL, _post_payload(post, 1), format="json")
        api.post(VOTE_URL, _post_payload(post, 1), format="json")
        alice.refresh_from_db()
        assert alice.post_karma == 0


@pytest.mark.django_db
class TestSerializerExposure:
    def test_post_list_exposes_score_and_user_vote(self, api, post, bob):
        Vote.objects.create(
            user=bob,
            content_type=ContentType.objects.get_for_model(Post),
            object_id=post.id,
            value=1,
        )
        api.force_authenticate(bob)
        url = reverse("api_v1:community-posts:community-posts", args=[post.community.slug])
        resp = api.get(url)
        row = next(p for p in resp.data["results"] if p["id"] == post.id)
        assert row["score"] == 1
        assert row["user_vote"] == 1

    def test_comment_list_exposes_score(self, api, comment, bob):
        Vote.objects.create(
            user=bob,
            content_type=ContentType.objects.get_for_model(Comment),
            object_id=comment.id,
            value=1,
        )
        api.force_authenticate(bob)
        url = reverse("api_v1:post-comments:post-comments", args=[comment.post_id])
        resp = api.get(url)
        row = resp.data["results"][0]
        assert row["score"] == 1
        assert row["user_vote"] == 1


@pytest.mark.django_db
class TestRecalculateKarma:
    def test_recalculate_fixes_drift(self, alice, post, bob, comment):
        Vote.objects.create(
            user=bob,
            content_type=ContentType.objects.get_for_model(Post),
            object_id=post.id,
            value=1,
        )
        Vote.objects.create(
            user=bob,
            content_type=ContentType.objects.get_for_model(Comment),
            object_id=comment.id,
            value=1,
        )
        # Corrupt the karma to simulate drift
        User.objects.filter(pk=alice.pk).update(post_karma=999, comment_karma=-5)
        call_command("recalculate_karma")
        alice.refresh_from_db()
        assert alice.post_karma == 1
        assert alice.comment_karma == 1

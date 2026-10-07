import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.comments.models import Comment
from apps.communities.models import Community
from apps.posts.models import Post

User = get_user_model()
MISSING_ID = 999_999
REPORT_URL = reverse("api_v1:moderation:report-create")


def sticky_url(pk):
    return reverse("api_v1:posts:post-sticky", args=[pk])


def approve_url(pk):
    return reverse("api_v1:posts:post-approve", args=[pk])


def post_revisions_url(pk):
    return reverse("api_v1:posts:post-revisions", args=[pk])


def comment_revisions_url(pk):
    return reverse("api_v1:comments:comment-revisions", args=[pk])


def _user(name):
    return User.objects.create_user(username=name, email=f"{name}@x.com", password="x")


@pytest.fixture
def owner(db):
    return _user("owner")


@pytest.fixture
def author(db):
    return _user("author")


@pytest.fixture
def stranger(db):
    return _user("stranger")


@pytest.fixture
def community(owner):
    return Community.objects.create(slug="py", name="Py", creator=owner)


@pytest.fixture
def held(author, community):
    return Post.objects.create(author=author, community=community, title="held", is_approved=False)


@pytest.fixture
def api():
    return APIClient()


@pytest.mark.django_db
class TestHeldPostProbing:
    def test_stranger_gets_404_on_sticky(self, api, stranger, held):
        api.force_authenticate(stranger)
        assert api.delete(sticky_url(held.pk)).status_code == 404
        held_resp = api.post(sticky_url(held.pk))
        missing_resp = api.post(sticky_url(MISSING_ID))
        assert held_resp.status_code == missing_resp.status_code == 404
        assert held_resp.data == missing_resp.data

    def test_stranger_gets_404_on_approve_and_reject(self, api, stranger, held):
        api.force_authenticate(stranger)
        assert api.delete(approve_url(held.pk)).status_code == 404
        held_resp = api.post(approve_url(held.pk))
        missing_resp = api.post(approve_url(MISSING_ID))
        assert held_resp.status_code == missing_resp.status_code == 404
        assert held_resp.data == missing_resp.data

    def test_author_still_gets_403_on_sticky(self, api, author, held):
        api.force_authenticate(author)
        assert api.post(sticky_url(held.pk)).status_code == 403

    def test_moderator_still_approves(self, api, owner, held):
        api.force_authenticate(owner)
        assert api.post(approve_url(held.pk)).status_code == 200

    def test_stranger_gets_404_on_post_revisions(self, api, stranger, held):
        api.force_authenticate(stranger)
        held_resp = api.get(post_revisions_url(held.pk))
        missing_resp = api.get(post_revisions_url(MISSING_ID))
        assert held_resp.status_code == missing_resp.status_code == 404
        assert held_resp.data == missing_resp.data

    def test_stranger_gets_404_on_comment_revisions(self, api, author, stranger, held):
        comment = Comment.objects.create(post=held, author=author, body="c")
        api.force_authenticate(stranger)
        held_resp = api.get(comment_revisions_url(comment.pk))
        missing_resp = api.get(comment_revisions_url(MISSING_ID))
        assert held_resp.status_code == missing_resp.status_code == 404
        assert held_resp.data == missing_resp.data

    def test_reporting_a_held_post_looks_like_a_missing_one(self, api, stranger, held):
        api.force_authenticate(stranger)
        held_resp = api.post(
            REPORT_URL, {"content_type": "post", "object_id": held.pk, "reason": "x"}, format="json"
        )
        missing_resp = api.post(
            REPORT_URL, {"content_type": "post", "object_id": 999_999, "reason": "x"}, format="json"
        )
        assert held_resp.status_code == missing_resp.status_code == 400
        assert held_resp.data == missing_resp.data

    def test_reporting_a_comment_on_a_held_post_looks_like_a_missing_one(
        self, api, author, stranger, held
    ):
        comment = Comment.objects.create(post=held, author=author, body="c")
        api.force_authenticate(stranger)
        resp = api.post(
            REPORT_URL,
            {"content_type": "comment", "object_id": comment.pk, "reason": "x"},
            format="json",
        )
        assert resp.status_code == 400
        assert "object_id" in resp.data

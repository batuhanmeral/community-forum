from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.comments.models import Comment
from apps.communities.models import Community
from apps.polls.models import Poll
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


def post_url(pk):
    return reverse("api_v1:posts:post-detail", args=[pk])


def comments_url(pk):
    return reverse("api_v1:post-comments:post-comments", args=[pk])


def comment_url(pk):
    return reverse("api_v1:comments:comment-detail", args=[pk])


def poll_url(pk):
    return reverse("api_v1:polls:poll-detail", args=[pk])


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

    def _same_as_missing(self, held_resp, missing_resp):
        assert held_resp.status_code == missing_resp.status_code == 404
        assert held_resp.data == missing_resp.data

    def test_post_detail_hides_held_post_like_a_missing_one(self, api, held):
        self._same_as_missing(api.get(post_url(held.pk)), api.get(post_url(MISSING_ID)))

    def test_comment_list_hides_held_post_like_a_missing_one(self, api, held):
        self._same_as_missing(api.get(comments_url(held.pk)), api.get(comments_url(MISSING_ID)))

    def test_comment_detail_hides_comment_on_held_post_like_a_missing_one(self, api, author, held):
        comment = Comment.objects.create(post=held, author=author, body="c")
        self._same_as_missing(api.get(comment_url(comment.pk)), api.get(comment_url(MISSING_ID)))

    def test_poll_of_held_post_looks_missing(self, api, held):
        poll = Poll.objects.create(post=held, closes_at=timezone.now() + timedelta(days=1))
        self._same_as_missing(api.get(poll_url(poll.pk)), api.get(poll_url(MISSING_ID)))

    def test_poll_of_deleted_post_looks_missing(self, api, author, community):
        post = Post.objects.create(
            author=author, community=community, title="gone", kind="poll", deleted_at=timezone.now()
        )
        poll = Poll.objects.create(post=post, closes_at=timezone.now() + timedelta(days=1))
        self._same_as_missing(api.get(poll_url(poll.pk)), api.get(poll_url(MISSING_ID)))

    def test_author_still_reads_own_held_post(self, api, author, held):
        api.force_authenticate(author)
        assert api.get(post_url(held.pk)).status_code == 200

    def test_stranger_write_on_held_post_looks_missing(self, api, stranger, held):
        api.force_authenticate(stranger)
        self._same_as_missing(
            api.patch(post_url(held.pk), {"title": "x"}, format="json"),
            api.patch(post_url(MISSING_ID), {"title": "x"}, format="json"),
        )
        self._same_as_missing(api.delete(post_url(held.pk)), api.delete(post_url(MISSING_ID)))

    def test_stranger_write_on_comment_of_held_post_looks_missing(
        self, api, author, stranger, held
    ):
        comment = Comment.objects.create(post=held, author=author, body="c")
        api.force_authenticate(stranger)
        self._same_as_missing(
            api.patch(comment_url(comment.pk), {"body": "x"}, format="json"),
            api.patch(comment_url(MISSING_ID), {"body": "x"}, format="json"),
        )
        self._same_as_missing(
            api.delete(comment_url(comment.pk)), api.delete(comment_url(MISSING_ID))
        )

    def test_author_still_patches_own_held_post(self, api, author, held):
        api.force_authenticate(author)
        resp = api.patch(post_url(held.pk), {"title": "new"}, format="json")
        assert resp.status_code == 200

    def test_stranger_still_gets_403_patching_approved_post(self, api, author, stranger, community):
        post = Post.objects.create(author=author, community=community, title="ok")
        api.force_authenticate(stranger)
        assert api.patch(post_url(post.pk), {"title": "x"}, format="json").status_code == 403


@pytest.mark.django_db
class TestReplyParentProbing:
    @pytest.fixture
    def visible(self, author, community):
        return Post.objects.create(author=author, community=community, title="visible")

    def _reply(self, api, post, parent):
        return api.post(comments_url(post.pk), {"body": "hi", "parent": parent}, format="json")

    @pytest.mark.parametrize("deleted", [False, True])
    def test_parent_on_a_held_post_looks_like_a_missing_parent(
        self, api, author, stranger, held, visible, deleted
    ):
        hidden = Comment.objects.create(
            post=held, author=author, body="c", deleted_at=timezone.now() if deleted else None
        )
        api.force_authenticate(stranger)
        hidden_resp = self._reply(api, visible, hidden.pk)
        missing_resp = self._reply(api, visible, MISSING_ID)
        assert hidden_resp.status_code == missing_resp.status_code == 400
        # The message echoes the requested id, so compare with that id masked.
        assert str(hidden_resp.data).replace(str(hidden.pk), "N") == str(missing_resp.data).replace(
            str(MISSING_ID), "N"
        )

    def test_reply_to_a_comment_on_the_same_post_still_works(self, api, author, stranger, visible):
        parent = Comment.objects.create(post=visible, author=author, body="c")
        api.force_authenticate(stranger)
        assert self._reply(api, visible, parent.pk).status_code == 201

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.comments.models import Comment, CommentRevision
from apps.comments.views import CommentDetailView
from apps.communities.models import Community, Membership
from apps.posts.models import Post

User = get_user_model()


def _user(name):
    return User.objects.create_user(username=name, email=f"{name}@x.com", password="x")


@pytest.fixture
def owner(db):
    return _user("owner")


@pytest.fixture
def author(db):
    return _user("author")


@pytest.fixture
def comment(owner, author):
    c = Community.objects.create(slug="races", name="Races", creator=owner)
    Membership.objects.create(user=author, community=c)
    post = Post.objects.create(author=owner, community=c, title="t")
    return Comment.objects.create(post=post, author=author, body="old body")


def test_mod_removal_during_comment_edit_stands(comment, author, owner):
    api = APIClient()
    api.force_authenticate(author)
    real = CommentDetailView.get_object

    def racing(self):
        obj = real(self)
        Comment.objects.filter(pk=comment.pk).update(deleted_at=timezone.now(), deleted_by=owner)
        return obj

    with patch.object(CommentDetailView, "get_object", autospec=True, side_effect=racing):
        resp = api.patch(
            reverse("api_v1:comments:comment-detail", args=[comment.id]),
            {"body": "edited"},
            format="json",
        )
    comment.refresh_from_db()
    assert resp.status_code == 400
    assert comment.deleted_at is not None and comment.deleted_by_id == owner.id
    assert comment.body == "old body"
    assert not CommentRevision.objects.filter(comment=comment).exists()


def test_comment_edit_locks_the_row(comment, author):
    api = APIClient()
    api.force_authenticate(author)
    with CaptureQueriesContext(connection) as ctx:
        resp = api.patch(
            reverse("api_v1:comments:comment-detail", args=[comment.id]),
            {"body": "edited"},
            format="json",
        )
    assert resp.status_code == 200
    assert any(
        'FROM "comments_comment"' in q["sql"] and q["sql"].endswith("FOR UPDATE")
        for q in ctx.captured_queries
    )

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.comments.models import Comment
from apps.communities.models import Community
from apps.moderation.models import Report
from apps.posts.models import Post

User = get_user_model()
REPORT_URL = reverse("api_v1:moderation:report-create")


def queue_url(slug):
    return reverse("api_v1:moderation:community-mod-reports", args=[slug])


def _user(name):
    return User.objects.create_user(username=name, email=f"{name}@x.com", password="x")


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def owner(db):
    return _user("owner")


@pytest.fixture
def reporter(db):
    return _user("reporter")


@pytest.fixture
def community(owner):
    return Community.objects.create(slug="py", name="Py", creator=owner)


@pytest.fixture
def post(owner, community):
    return Post.objects.create(author=owner, community=community, title="Reported title")


def _report(reporter, target):
    return Report.objects.create(
        reporter=reporter,
        content_type=ContentType.objects.get_for_model(target.__class__),
        object_id=target.pk,
        reason="spam",
    )


def _rows(api, owner):
    api.force_authenticate(owner)
    return api.get(queue_url("py")).data["results"]


@pytest.mark.django_db
class TestReportQueue:
    def test_moderators_do_not_see_the_reporter(self, api, owner, reporter, post):
        _report(reporter, post)
        row = _rows(api, owner)[0]
        assert "reporter" not in row
        assert "reporter_username" not in row

    def test_reporter_identity_absent_from_create_response(self, api, reporter, post):
        api.force_authenticate(reporter)
        resp = api.post(
            REPORT_URL, {"content_type": "post", "object_id": post.pk, "reason": "x"}, format="json"
        )
        assert resp.status_code == 201
        assert "reporter" not in resp.data

    def test_post_preview(self, api, owner, reporter, post):
        _report(reporter, post)
        preview = _rows(api, owner)[0]["target_preview"]
        assert preview == {
            "text": "Reported title",
            "link": f"/posts/{post.pk}",
            "is_deleted": False,
        }

    def test_comment_preview_links_to_the_comment(self, api, owner, reporter, post):
        comment = Comment.objects.create(post=post, author=owner, body="x" * 300)
        _report(reporter, comment)
        preview = _rows(api, owner)[0]["target_preview"]
        assert preview["link"] == f"/posts/{post.pk}#comment-{comment.pk}"
        assert preview["text"] == "x" * 140

    def test_removed_comment_preview_is_masked(self, api, owner, reporter, post):
        author = _user("author")
        comment = Comment.objects.create(
            post=post, author=author, body="secret", deleted_at=timezone.now(), deleted_by=owner
        )
        _report(reporter, comment)
        preview = _rows(api, owner)[0]["target_preview"]
        assert preview["text"] == "[removed]"
        assert preview["is_deleted"] is True

    def test_query_count_does_not_grow_with_reports(self, api, owner, reporter, post):
        _report(reporter, post)
        api.force_authenticate(owner)
        with CaptureQueriesContext(connection) as one:
            api.get(queue_url("py"))
        for i in range(4):
            c = Comment.objects.create(post=post, author=owner, body=f"c{i}")
            _report(reporter, c)
        with CaptureQueriesContext(connection) as five:
            api.get(queue_url("py"))
        assert len(five) <= len(one) + 1  # one extra prefetch query for the comment content type

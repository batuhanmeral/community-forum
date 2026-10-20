import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.comments.models import Comment
from apps.communities.models import Community, Membership
from apps.moderation.models import ModAction, Report
from apps.posts.models import Post

User = get_user_model()


def _user(name):
    return User.objects.create_user(username=name, email=f"{name}@x.com", password="x")


@pytest.fixture
def owner(db):
    return _user("owner")


@pytest.fixture
def community(owner):
    return Community.objects.create(slug="py", name="Python", creator=owner)


@pytest.fixture
def api(owner):
    client = APIClient()
    client.force_authenticate(owner)
    return client


def _url(name):
    return reverse(f"api_v1:moderation:{name}", args=["py"])


def test_ten_reports_within_eight_queries(api, community, django_assert_max_num_queries):
    reporter = _user("reporter")
    post_ct = ContentType.objects.get_for_model(Post)
    comment_ct = ContentType.objects.get_for_model(Comment)
    for i in range(5):
        author = _user(f"a{i}")
        post = Post.objects.create(author=author, community=community, kind="text", title=f"p{i}")
        comment = Comment.objects.create(post=post, author=author, body="c")
        Report.objects.create(
            reporter=reporter, content_type=post_ct, object_id=post.pk, reason="x"
        )
        Report.objects.create(
            reporter=reporter, content_type=comment_ct, object_id=comment.pk, reason="x"
        )
    with django_assert_max_num_queries(8):
        resp = api.get(_url("community-mod-reports"))
    assert len(resp.data["results"]) == 10


def test_ten_bans_within_four_queries(api, owner, community, django_assert_max_num_queries):
    for i in range(10):
        Membership.objects.create(
            user=_user(f"b{i}"),
            community=community,
            is_banned=True,
            banned_by=owner,
            banned_at=timezone.now(),
        )
    with django_assert_max_num_queries(4):
        resp = api.get(_url("community-mod-bans"))
    assert len(resp.data["results"]) == 10


def test_ten_mod_log_rows_within_four_queries(api, community, django_assert_max_num_queries):
    post_ct = ContentType.objects.get_for_model(Post)
    for i in range(10):
        ModAction.objects.create(
            community=community,
            actor=_user(f"m{i}"),
            action=ModAction.Action.POST_PIN,
            content_type=post_ct,
            object_id=i + 1,
        )
    with django_assert_max_num_queries(4):
        resp = api.get(_url("community-mod-log"))
    assert len(resp.data["results"]) == 10

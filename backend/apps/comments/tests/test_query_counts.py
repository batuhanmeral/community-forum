import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from rest_framework.test import APIClient

from apps.comments.models import Comment
from apps.communities.models import Community
from apps.posts.models import Post
from apps.saves.models import SavedItem
from apps.votes.models import Vote

User = get_user_model()

COMMENT_COUNT = 30
VOTERS_PER_COMMENT = 20


@pytest.fixture
def viewer(db):
    return User.objects.create_user(username="viewer", email="viewer@x.com", password="x")


@pytest.fixture
def viewer_api(viewer):
    api = APIClient()
    api.force_authenticate(viewer)
    return api


@pytest.fixture
def post(viewer):
    community = Community.objects.create(slug="py", name="Python", creator=viewer)
    return Post.objects.create(author=viewer, community=community, kind="text", title="t")


@pytest.fixture
def comments(post, viewer):
    comments = Comment.objects.bulk_create(
        [Comment(post=post, author=post.author, body=f"c{i}") for i in range(COMMENT_COUNT)]
    )
    others = User.objects.bulk_create(
        [User(username=f"other{i}", email=f"o{i}@x.com") for i in range(VOTERS_PER_COMMENT)]
    )
    ct = ContentType.objects.get_for_model(Comment)
    Vote.objects.bulk_create(
        [
            Vote(user=other, content_type=ct, object_id=comment.pk, value=1)
            for comment in comments
            for other in others
        ]
    )
    SavedItem.objects.bulk_create(
        [
            SavedItem(user=other, content_type=ct, object_id=comment.pk)
            for comment in comments
            for other in others
        ]
    )
    # Newest comments, so they sit on the first page of every list.
    voted, saved = comments[-1], comments[-2]
    Vote.objects.create(user=viewer, content_type=ct, object_id=voted.pk, value=1)
    SavedItem.objects.create(user=viewer, content_type=ct, object_id=saved.pk)
    return comments


def urls(post):
    return [
        reverse("api_v1:post-comments:post-comments", args=[post.pk]),
        reverse("api_v1:comments:user-comments", args=[post.author.username]),
    ]


@pytest.mark.parametrize("which", [0, 1])
def test_comment_lists_load_only_viewer_rows(
    viewer_api, post, comments, which, rows_loaded, django_assert_max_num_queries
):
    with rows_loaded(Vote, SavedItem) as loaded, django_assert_max_num_queries(6):
        resp = viewer_api.get(urls(post)[which])
    n = len(resp.data["results"])
    assert n >= 20
    assert loaded[Vote] <= n and loaded[SavedItem] <= n


@pytest.mark.parametrize("which", [0, 1])
def test_comment_viewer_flags(viewer_api, post, comments, which):
    by_id = {c["id"]: c for c in viewer_api.get(urls(post)[which]).data["results"]}
    voted, saved = comments[-1], comments[-2]
    assert by_id[voted.id]["user_vote"] == 1
    assert by_id[saved.id]["user_vote"] is None
    assert by_id[saved.id]["is_saved"] is True
    assert by_id[voted.id]["is_saved"] is False

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.comments.models import Comment
from apps.comments.views import _annotate_score, _apply_comment_sort
from apps.communities.models import Community
from apps.posts.models import Post

User = get_user_model()


@pytest.mark.django_db
def test_thread_arrives_in_one_page():
    alice = User.objects.create_user(username="alice", email="a@x.com", password="x")
    community = Community.objects.create(slug="py", name="Py", creator=alice)
    post = Post.objects.create(author=alice, community=community, title="t")
    first = Comment.objects.create(post=post, author=alice, body="first")
    for i in range(24):
        Comment.objects.create(post=post, author=alice, body=f"c{i}")
    Comment.objects.create(post=post, author=alice, body="reply", parent=first)

    data = APIClient().get(reverse("api_v1:post-comments:post-comments", args=[post.id])).data
    assert data["count"] == 26
    assert len(data["results"]) == 26
    assert data["next"] is None


@pytest.mark.django_db
@pytest.mark.parametrize("sort", ["best", "top", "new", "old", "controversial"])
def test_every_sort_ends_with_an_id_tiebreaker(sort):
    # Postgres happens to return ties in id order, so assert the ordering itself
    # to guarantee stable page boundaries regardless of the query plan.
    ordering = _apply_comment_sort(_annotate_score(Comment.objects.all()), sort).query.order_by
    assert ordering[-1] == "id"

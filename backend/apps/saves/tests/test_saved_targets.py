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
SAVED = reverse("api_v1:saves:saved-list")


def _user(name):
    return User.objects.create_user(username=name, email=f"{name}@x.com", password="x")


def _save(user, target):
    SavedItem.objects.create(
        user=user, content_type=ContentType.objects.get_for_model(type(target)), object_id=target.id
    )


def _vote(user, target, value=1):
    Vote.objects.create(
        user=user,
        content_type=ContentType.objects.get_for_model(type(target)),
        object_id=target.id,
        value=value,
    )


@pytest.mark.django_db
def test_saved_targets_carry_scores_counts_and_my_vote():
    alice, bob = _user("alice"), _user("bob")
    community = Community.objects.create(slug="py", name="Py", creator=alice)
    post = Post.objects.create(author=alice, community=community, title="t")
    comment = Comment.objects.create(post=post, author=alice, body="c")
    _vote(bob, post)
    _vote(bob, comment)
    _save(bob, post)
    _save(bob, comment)

    client = APIClient()
    client.force_authenticate(bob)
    targets = {row["target_type"]: row["target"] for row in client.get(SAVED).data["results"]}
    assert targets["post"]["score"] == 1
    assert targets["post"]["comment_count"] == 1
    assert targets["post"]["user_vote"] == 1
    assert targets["comment"]["score"] == 1
    assert targets["comment"]["user_vote"] == 1


@pytest.mark.django_db
def test_saved_post_that_became_pending_stays_hidden_from_saver():
    alice, bob = _user("alice"), _user("bob")
    community = Community.objects.create(slug="py", name="Py", creator=alice)
    post = Post.objects.create(author=alice, community=community, title="t", is_approved=False)
    _save(bob, post)

    client = APIClient()
    client.force_authenticate(bob)
    rows = client.get(SAVED).data["results"]
    assert [row["target"] for row in rows] == [None]


@pytest.mark.django_db
def test_saved_list_query_count_does_not_grow_with_items(django_assert_max_num_queries):
    alice, bob = _user("alice"), _user("bob")
    community = Community.objects.create(slug="py", name="Py", creator=alice)
    for i in range(5):
        post = Post.objects.create(author=alice, community=community, title=f"t{i}")
        _save(bob, post)
        _save(bob, Comment.objects.create(post=post, author=alice, body="c"))

    client = APIClient()
    client.force_authenticate(bob)
    with django_assert_max_num_queries(12):
        assert len(client.get(SAVED).data["results"]) == 10

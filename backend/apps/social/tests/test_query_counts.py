import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APIClient

from apps.social.models import Block, Follow

User = get_user_model()

LEADERBOARD = reverse("api_v1:users:users-leaderboard")
PROFILE_U0 = reverse("api_v1:users:users-profile", args=["u0"])
FOLLOWERS_ME = reverse("api_v1:social:user-followers", args=["me"])
FOLLOWING_ME = reverse("api_v1:social:user-following", args=["me"])
BLOCKED_ME = reverse("api_v1:social:user-blocked-list")
SEARCH = reverse("api_v1:search:search")
SEARCH_USERS = SEARCH + "?type=user&q=member"


def make_user(name):
    return User.objects.create_user(
        username=name, email=f"{name}@x.com", password="x", bio="hub member"
    )


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()


@pytest.fixture
def me(db):
    return make_user("me")


@pytest.fixture
def api(me):
    client = APIClient()
    client.force_authenticate(me)
    return client


@pytest.fixture
def me_with_ten_followed_followers_and_blocked(me):
    for i in range(10):
        user = make_user(f"u{i}")
        Follow.objects.create(follower=user, followed=me)
        Follow.objects.create(follower=me, followed=user)
        Block.objects.create(blocker=me, blocked=make_user(f"b{i}"))


@pytest.mark.parametrize(
    "url, ceiling",
    [
        (LEADERBOARD, 3),
        (PROFILE_U0, 3),
        (FOLLOWERS_ME, 4),
        (FOLLOWING_ME, 4),
        (BLOCKED_ME, 4),
        (SEARCH_USERS, 4),
    ],
)
def test_user_lists_have_constant_queries(
    api, me_with_ten_followed_followers_and_blocked, url, ceiling, django_assert_max_num_queries
):
    with django_assert_max_num_queries(ceiling):
        assert api.get(url).status_code == 200


def test_follow_flags_are_per_viewer(api, me):
    carol, dave = make_user("carol"), make_user("dave")
    Follow.objects.create(follower=me, followed=carol)
    Follow.objects.create(follower=carol, followed=dave)
    Block.objects.create(blocker=me, blocked=dave)
    rows = {u["username"]: u for u in api.get(SEARCH_USERS).data["results"]}
    assert rows["carol"]["is_following"] is True and rows["dave"]["is_following"] is False
    assert rows["dave"]["is_blocked"] is True and rows["carol"]["is_blocked"] is False
    assert rows["carol"]["followers_count"] == 1 and rows["carol"]["following_count"] == 1
    assert rows["dave"]["followers_count"] == 1 and rows["dave"]["following_count"] == 0
    assert rows["me"]["is_following"] is False and rows["me"]["is_blocked"] is False
    assert rows["me"]["followers_count"] == 0 and rows["me"]["following_count"] == 1


def test_anonymous_viewer_sees_counts_but_no_relations(me):
    carol = make_user("carol")
    Follow.objects.create(follower=me, followed=carol)
    rows = {u["username"]: u for u in APIClient().get(SEARCH_USERS).data["results"]}
    assert rows["carol"]["followers_count"] == 1
    assert rows["carol"]["is_following"] is False and rows["carol"]["is_blocked"] is False
    assert rows["me"]["following_count"] == 1

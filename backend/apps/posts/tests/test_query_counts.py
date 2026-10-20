import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from rest_framework.test import APIClient

from apps.common.viewer import viewer_vote
from apps.communities.models import Community, Membership
from apps.posts.models import Post, PostRevision
from apps.saves.models import SavedItem
from apps.social.models import Follow
from apps.votes.models import Vote

User = get_user_model()

POST_COUNT = 20
VOTERS_PER_POST = 50
SAVERS_PER_POST = 10

FEED = reverse("api_v1:feed:feed")
COMMUNITY_POSTS = reverse("api_v1:community-posts:community-posts", args=["py"])
USER_POSTS = reverse("api_v1:posts:user-posts", args=["author"])
SEARCH_POSTS = reverse("api_v1:search:search") + "?type=post&q=widget"
TRENDING_POSTS = reverse("api_v1:search:trending-posts")


def post_detail(pk):
    return reverse("api_v1:posts:post-detail", args=[pk])


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def anon_api():
    return APIClient()


@pytest.fixture
def author(db):
    return User.objects.create_user(username="author", email="author@x.com", password="x")


@pytest.fixture
def viewer(db):
    return User.objects.create_user(username="viewer", email="viewer@x.com", password="x")


@pytest.fixture
def community(author, viewer):
    c = Community.objects.create(slug="py", name="Python", creator=author)
    Membership.objects.create(user=viewer, community=c)
    return c


@pytest.fixture
def posts(author, viewer, community):
    posts = [
        Post.objects.create(author=author, community=community, kind="text", title=f"widget {i}")
        for i in range(POST_COUNT)
    ]
    others = User.objects.bulk_create(
        [User(username=f"other{i}", email=f"other{i}@x.com") for i in range(VOTERS_PER_POST)]
    )
    ct = ContentType.objects.get_for_model(Post)
    Vote.objects.bulk_create(
        [
            Vote(user=other, content_type=ct, object_id=post.pk, value=1)
            for post in posts
            for other in others
        ]
    )
    SavedItem.objects.bulk_create(
        [
            SavedItem(user=other, content_type=ct, object_id=post.pk)
            for post in posts
            for other in others[:SAVERS_PER_POST]
        ]
    )
    Vote.objects.create(user=viewer, content_type=ct, object_id=posts[0].pk, value=1)
    Vote.objects.create(user=viewer, content_type=ct, object_id=posts[1].pk, value=-1)
    SavedItem.objects.create(user=viewer, content_type=ct, object_id=posts[2].pk)
    return posts


@pytest.fixture
def viewer_api(api, viewer):
    api.force_authenticate(viewer)
    return api


@pytest.mark.parametrize(
    "url", [FEED, FEED + "?scope=all", COMMUNITY_POSTS, USER_POSTS, SEARCH_POSTS, TRENDING_POSTS]
)
def test_post_lists_load_only_viewer_rows(
    viewer_api, posts, url, rows_loaded, django_assert_max_num_queries
):
    with rows_loaded(Vote, SavedItem) as loaded, django_assert_max_num_queries(12):
        resp = viewer_api.get(url)
    n = len(resp.data["results"])
    assert n == POST_COUNT
    assert loaded[Vote] <= n and loaded[SavedItem] <= n


def test_other_users_votes_and_saves_are_not_the_viewers(viewer_api, posts):
    by_id = {p["id"]: p for p in viewer_api.get(FEED).data["results"]}
    votes = (
        by_id[posts[0].id]["user_vote"],
        by_id[posts[1].id]["user_vote"],
        by_id[posts[3].id]["user_vote"],
    )
    assert votes == (1, -1, None)
    assert by_id[posts[2].id]["is_saved"] is True
    assert by_id[posts[3].id]["is_saved"] is False


def test_anonymous_feed_loads_no_vote_rows(anon_api, posts, rows_loaded):
    with rows_loaded(Vote, SavedItem) as loaded:
        resp = anon_api.get(FEED + "?scope=all")
    assert len(resp.data["results"]) == POST_COUNT
    assert loaded[Vote] == 0 and loaded[SavedItem] == 0
    assert resp.data["results"][0]["user_vote"] is None
    assert resp.data["results"][0]["is_saved"] is False


def test_patch_response_keeps_viewer_vote(api, author, posts):
    ct = ContentType.objects.get_for_model(Post)
    Vote.objects.create(user=author, content_type=ct, object_id=posts[3].pk, value=1)
    api.force_authenticate(author)
    resp = api.patch(post_detail(posts[3].pk), {"title": "new"}, format="json")
    assert resp.status_code == 200
    assert resp.data["user_vote"] == 1


def test_viewer_vote_queries_when_object_was_not_prefetched(viewer, posts):
    assert viewer_vote(Post.objects.get(pk=posts[1].pk), viewer) == -1


@pytest.fixture
def moderator(community):
    mod = User.objects.create_user(username="mod", email="mod@x.com", password="x")
    Membership.objects.create(user=mod, community=community, role="moderator")
    return mod


def test_ten_revisions_within_three_queries(api, author, community, django_assert_max_num_queries):
    post = Post.objects.create(author=author, community=community, kind="text", title="t")
    for i in range(10):
        editor = User.objects.create_user(username=f"ed{i}", email=f"ed{i}@x.com", password="x")
        PostRevision.objects.create(post=post, title="old", body="b", edited_by=editor)
    api.force_authenticate(author)
    with django_assert_max_num_queries(3):
        resp = api.get(reverse("api_v1:posts:post-revisions", args=[post.pk]))
    assert len(resp.data["results"]) == 10


def test_ten_held_posts_within_seven_queries(
    api, moderator, community, django_assert_max_num_queries
):
    for i in range(10):
        writer = User.objects.create_user(username=f"w{i}", email=f"w{i}@x.com", password="x")
        Post.objects.create(
            author=writer, community=community, kind="text", title=f"held {i}", is_approved=False
        )
    api.force_authenticate(moderator)
    url = reverse("api_v1:community-posts:community-approval-queue", args=["py"])
    with django_assert_max_num_queries(7):
        resp = api.get(url)
    assert len(resp.data["results"]) == 10


def test_following_feed_with_ten_posts_within_five_queries(
    api, viewer, community, django_assert_max_num_queries
):
    for i in range(10):
        writer = User.objects.create_user(username=f"f{i}", email=f"f{i}@x.com", password="x")
        Follow.objects.create(follower=viewer, followed=writer)
        Post.objects.create(author=writer, community=community, kind="text", title=f"p {i}")
    api.force_authenticate(viewer)
    with django_assert_max_num_queries(5):
        resp = api.get(reverse("api_v1:feed:feed-following"))
    assert len(resp.data["results"]) == 10

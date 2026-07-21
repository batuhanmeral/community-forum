import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from rest_framework.test import APIClient

from apps.communities.models import Community, Membership
from apps.posts.models import Post
from apps.social.models import Follow
from apps.votes.models import Vote

User = get_user_model()
FEED = reverse("api_v1:feed:feed")
FOLLOWING = reverse("api_v1:feed:feed-following")


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="alice", email="a@x.com", password="x")


@pytest.fixture
def bob(db):
    return User.objects.create_user(username="bob", email="b@x.com", password="x")


@pytest.fixture
def carol(db):
    return User.objects.create_user(username="carol", email="c@x.com", password="x")


@pytest.fixture
def joined_community(bob):
    c = Community.objects.create(slug="py", name="Python", creator=bob)
    return c


@pytest.fixture
def other_community(carol):
    return Community.objects.create(slug="rust", name="Rust", creator=carol)


def _post(author, community, **kwargs):
    return Post.objects.create(
        author=author, community=community, kind="text", title=kwargs.pop("title", "t"), **kwargs
    )


@pytest.mark.django_db
class TestFeed:
    def test_authed_sees_only_joined_communities(self, api, alice, bob, carol, joined_community, other_community):
        Membership.objects.create(user=alice, community=joined_community)
        mine = _post(bob, joined_community, title="in-feed")
        _post(carol, other_community, title="not-in-feed")
        api.force_authenticate(alice)
        resp = api.get(FEED)
        assert resp.status_code == 200
        ids = [p["id"] for p in resp.data["results"]]
        assert ids == [mine.id]

    def test_pinned_always_on_top(self, api, alice, bob, joined_community):
        Membership.objects.create(user=alice, community=joined_community)
        _post(bob, joined_community, title="new")
        old_pinned = _post(bob, joined_community, title="pin", is_pinned=True)
        api.force_authenticate(alice)
        resp = api.get(FEED)
        assert resp.data["results"][0]["id"] == old_pinned.id

    def test_nsfw_hidden_by_default(self, api, alice, bob, joined_community):
        Membership.objects.create(user=alice, community=joined_community)
        _post(bob, joined_community, title="safe")
        nsfw = _post(bob, joined_community, title="nsfw", is_nsfw=True)
        api.force_authenticate(alice)
        ids = [p["id"] for p in api.get(FEED).data["results"]]
        assert nsfw.id not in ids

    def test_nsfw_show_includes(self, api, alice, bob, joined_community):
        Membership.objects.create(user=alice, community=joined_community)
        nsfw = _post(bob, joined_community, title="nsfw", is_nsfw=True)
        api.force_authenticate(alice)
        resp = api.get(FEED, {"nsfw": "show"})
        ids = [p["id"] for p in resp.data["results"]]
        assert nsfw.id in ids

    def test_anonymous_sees_popular_without_nsfw(self, api, bob, joined_community):
        p = _post(bob, joined_community, title="safe")
        _post(bob, joined_community, title="nsfw", is_nsfw=True)
        Vote.objects.create(
            user=bob,
            content_type=ContentType.objects.get_for_model(Post),
            object_id=p.id,
            value=1,
        )
        resp = api.get(FEED)
        assert resp.status_code == 200
        ids = [r["id"] for r in resp.data["results"]]
        assert p.id in ids
        # nsfw hidden for anon even with ?nsfw=show
        ids_show = [r["id"] for r in api.get(FEED, {"nsfw": "show"}).data["results"]]
        assert all(Post.objects.get(pk=i).is_nsfw is False for i in ids_show)

    def test_top_sort_by_score(self, api, alice, bob, joined_community):
        Membership.objects.create(user=alice, community=joined_community)
        low = _post(bob, joined_community, title="low")
        high = _post(bob, joined_community, title="high")
        Vote.objects.create(
            user=alice,
            content_type=ContentType.objects.get_for_model(Post),
            object_id=high.id,
            value=1,
        )
        api.force_authenticate(alice)
        ids = [p["id"] for p in api.get(FEED, {"sort": "top"}).data["results"]]
        assert ids.index(high.id) < ids.index(low.id)


@pytest.mark.django_db
class TestFollowingFeed:
    def test_anonymous_rejected(self, api):
        assert api.get(FOLLOWING).status_code == 401

    def test_returns_only_followed_authors(self, api, alice, bob, carol, joined_community, other_community):
        Follow.objects.create(follower=alice, followed=bob)
        from_bob = _post(bob, joined_community, title="from-bob")
        _post(carol, other_community, title="from-carol")
        api.force_authenticate(alice)
        resp = api.get(FOLLOWING)
        ids = [p["id"] for p in resp.data["results"]]
        assert ids == [from_bob.id]

    def test_deleted_posts_excluded(self, api, alice, bob, joined_community):
        from django.utils import timezone

        Follow.objects.create(follower=alice, followed=bob)
        deleted = _post(bob, joined_community, title="gone")
        deleted.deleted_at = timezone.now()
        deleted.deleted_by = bob
        deleted.save()
        api.force_authenticate(alice)
        ids = [p["id"] for p in api.get(FOLLOWING).data["results"]]
        assert deleted.id not in ids


@pytest.mark.django_db
class TestFeedContent:
    def test_deleted_posts_excluded_from_feed(self, api, alice, bob, joined_community):
        from django.utils import timezone

        Membership.objects.create(user=alice, community=joined_community)
        visible = _post(bob, joined_community, title="visible")
        deleted = _post(bob, joined_community, title="gone")
        deleted.deleted_at = timezone.now()
        deleted.deleted_by = bob
        deleted.save()
        api.force_authenticate(alice)
        ids = [p["id"] for p in api.get(FEED).data["results"]]
        assert visible.id in ids
        assert deleted.id not in ids

    def test_author_username_and_comment_count(self, api, alice, bob, joined_community):
        from apps.comments.models import Comment

        Membership.objects.create(user=alice, community=joined_community)
        post = _post(bob, joined_community, title="counted")
        Comment.objects.create(post=post, author=alice, body="one")
        Comment.objects.create(post=post, author=bob, body="two")
        api.force_authenticate(alice)
        (row,) = api.get(FEED).data["results"]
        assert row["author_username"] == "bob"
        assert row["comment_count"] == 2

    def test_comment_count_does_not_inflate_score(self, api, alice, bob, joined_community):
        Membership.objects.create(user=alice, community=joined_community)
        post = _post(bob, joined_community, title="scored")
        Vote.objects.create(
            user=alice,
            content_type=ContentType.objects.get_for_model(Post),
            object_id=post.id,
            value=1,
        )
        from apps.comments.models import Comment

        for i in range(3):
            Comment.objects.create(post=post, author=bob, body=f"c{i}")
        api.force_authenticate(alice)
        (row,) = api.get(FEED).data["results"]
        assert row["score"] == 1
        assert row["comment_count"] == 3

    def test_scope_all_ignores_membership(self, api, alice, bob, carol, joined_community, other_community):
        _post(bob, joined_community, title="a")
        outside = _post(carol, other_community, title="b")
        api.force_authenticate(alice)  # alice is member of nothing
        assert api.get(FEED).data["results"] == []
        ids = [p["id"] for p in api.get(FEED, {"scope": "all"}).data["results"]]
        assert outside.id in ids

    def test_feed_query_count_is_constant(self, api, alice, bob, joined_community, django_assert_max_num_queries):
        Membership.objects.create(user=alice, community=joined_community)
        for i in range(15):
            p = _post(bob, joined_community, title=f"p{i}")
            Vote.objects.create(
                user=bob,
                content_type=ContentType.objects.get_for_model(Post),
                object_id=p.id,
                value=1,
            )
        api.force_authenticate(alice)
        with django_assert_max_num_queries(12):
            resp = api.get(FEED)
        assert len(resp.data["results"]) == 15

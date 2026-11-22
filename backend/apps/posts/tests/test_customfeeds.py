import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.communities.models import Community, Membership
from apps.posts.models import CustomFeed, CustomFeedItem, HiddenPost, Post

User = get_user_model()


@pytest.fixture
def cw(db):
    owner = User.objects.create_user(username="owner", email="o@example.com")
    viewer = User.objects.create_user(username="viewer", email="v@example.com")
    author = User.objects.create_user(username="author", email="a@example.com")
    py = Community.objects.create(slug="py", name="Py", creator=author)
    js = Community.objects.create(slug="js", name="Js", creator=author)
    rust = Community.objects.create(slug="rust", name="Rust", creator=author)
    posts = {
        slug: Post.objects.create(author=author, community=c, title=f"{slug} post", body="b")
        for slug, c in (("py", py), ("js", js), ("rust", rust))
    }
    return {
        "owner": owner,
        "viewer": viewer,
        "author": author,
        "py": py,
        "js": js,
        "rust": rust,
        "posts": posts,
    }


def client(user=None):
    api = APIClient()
    if user:
        api.force_authenticate(user)
    return api


def make_feed(user, **extra):
    payload = {"name": "My Feed", "communities": ["py", "js"], **extra}
    return client(user).post("/api/v1/users/me/feeds/", payload, format="json")


def feed_url(owner, slug, tail=""):
    return f"/api/v1/users/{owner.username}/feeds/{slug}/{tail}"


def ids(response):
    return [row["id"] for row in response.data["results"]]


@pytest.mark.django_db
class TestFeedCrud:
    def test_create_derives_unique_slug_and_lists_communities(self, cw):
        first = make_feed(cw["owner"])
        assert first.status_code == 201
        assert first.data["slug"] == "my-feed"
        assert first.data["owner_username"] == "owner"
        assert first.data["communities"] == ["js", "py"]
        assert first.data["is_public"] is False
        second = make_feed(cw["owner"])
        assert second.data["slug"] == "my-feed-2"
        assert make_feed(cw["viewer"]).data["slug"] == "my-feed"

    def test_slug_falls_back_when_name_has_no_letters(self, cw):
        assert make_feed(cw["owner"], name="🔥🔥").data["slug"] == "feed"

    def test_requires_login_to_create(self, cw):
        assert (
            client().post("/api/v1/users/me/feeds/", {"name": "x"}, format="json").status_code
            == 401
        )

    @pytest.mark.parametrize(
        "payload",
        [
            {"name": ""},
            {"name": "x" * 51},
            {"name": "ok", "description": "d" * 281},
            {"name": "ok", "communities": ["nope"]},
            {"name": "ok", "communities": "py"},
        ],
    )
    def test_validation(self, cw, payload):
        response = client(cw["owner"]).post("/api/v1/users/me/feeds/", payload, format="json")
        assert response.status_code == 400

    def test_limits(self, cw, monkeypatch):
        monkeypatch.setattr("apps.posts.customfeeds.MAX_FEEDS_PER_USER", 2)
        monkeypatch.setattr("apps.posts.customfeeds.MAX_COMMUNITIES_PER_FEED", 2)
        assert make_feed(cw["owner"], name="a").status_code == 201
        assert make_feed(cw["owner"], name="b").status_code == 201
        assert make_feed(cw["owner"], name="c").status_code == 400
        assert make_feed(cw["viewer"], communities=["py", "js", "rust"]).status_code == 400

    def test_owner_updates_replaces_communities_and_keeps_slug(self, cw):
        make_feed(cw["owner"])
        response = client(cw["owner"]).patch(
            feed_url(cw["owner"], "my-feed"),
            {"name": "Renamed", "is_public": True, "communities": ["rust", "rust", "py"]},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["slug"] == "my-feed"
        assert response.data["name"] == "Renamed"
        assert response.data["communities"] == ["py", "rust"]
        assert CustomFeedItem.objects.count() == 2

    def test_only_the_owner_can_change_or_delete(self, cw):
        make_feed(cw["owner"], is_public=True)
        url = feed_url(cw["owner"], "my-feed")
        for api in (client(cw["viewer"]), client()):
            assert api.patch(url, {"name": "x"}, format="json").status_code in (401, 403)
            assert api.delete(url).status_code in (401, 403)
        assert client(cw["owner"]).delete(url).status_code == 204
        assert CustomFeed.objects.count() == 0 and CustomFeedItem.objects.count() == 0

    def test_listing_shows_public_to_others_and_everything_to_the_owner(self, cw):
        make_feed(cw["owner"], name="Private")
        make_feed(cw["owner"], name="Public", is_public=True)
        url = "/api/v1/users/owner/feeds/"
        assert [r["slug"] for r in client(cw["owner"]).get(url).data["results"]] == [
            "private",
            "public",
        ]
        for api in (client(cw["viewer"]), client()):
            assert [r["slug"] for r in api.get(url).data["results"]] == ["public"]
        assert client().get("/api/v1/users/nobody/feeds/").status_code == 404

    def test_my_list_endpoint(self, cw):
        make_feed(cw["owner"], name="Private")
        rows = client(cw["owner"]).get("/api/v1/users/me/feeds/").data["results"]
        assert [r["slug"] for r in rows] == ["private"]


@pytest.mark.django_db
class TestFeedVisibility:
    def test_private_feed_is_404_for_everyone_but_the_owner(self, cw):
        make_feed(cw["owner"])
        for tail in ("", "posts/"):
            url = feed_url(cw["owner"], "my-feed", tail)
            assert client(cw["owner"]).get(url).status_code == 200
            assert client(cw["viewer"]).get(url).status_code == 404
            assert client().get(url).status_code == 404
        # Same answer as a feed that does not exist, so existence cannot be probed.
        missing = client(cw["viewer"]).get(feed_url(cw["owner"], "nope"))
        hidden = client(cw["viewer"]).get(feed_url(cw["owner"], "my-feed"))
        assert missing.status_code == hidden.status_code == 404
        assert missing.data == hidden.data

    def test_public_feed_is_readable_by_anyone_but_read_only(self, cw):
        make_feed(cw["owner"], is_public=True)
        url = feed_url(cw["owner"], "my-feed")
        assert client().get(url).data["communities"] == ["js", "py"]
        assert client(cw["viewer"]).get(url + "posts/").status_code == 200
        assert client(cw["viewer"]).put(url, {"name": "x"}, format="json").status_code == 403

    def test_deactivated_owner_feeds_are_gone(self, cw):
        make_feed(cw["owner"], is_public=True)
        User.objects.filter(pk=cw["owner"].pk).update(is_active=False)
        assert client().get(feed_url(cw["owner"], "my-feed")).status_code == 404


@pytest.mark.django_db
class TestFeedPosts:
    def test_posts_come_only_from_member_communities(self, cw):
        make_feed(cw["owner"], is_public=True)
        response = client(cw["viewer"]).get(feed_url(cw["owner"], "my-feed", "posts/"))
        assert sorted(ids(response)) == sorted([cw["posts"]["py"].pk, cw["posts"]["js"].pk])

    def test_reuses_sorting_time_window_and_answered_filters(self, cw):
        make_feed(cw["owner"], is_public=True)
        old = cw["posts"]["py"]
        Post.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timezone.timedelta(days=40)
        )
        Post.objects.filter(pk=cw["posts"]["js"].pk).update(is_question=True)
        url = feed_url(cw["owner"], "my-feed", "posts/")
        api = client(cw["viewer"])
        assert ids(api.get(url + "?sort=new"))[0] == cw["posts"]["js"].pk
        assert ids(api.get(url + "?t=week")) == [cw["posts"]["js"].pk]
        assert ids(api.get(url + "?answered=false")) == [cw["posts"]["js"].pk]

    def test_hidden_nsfw_held_and_deleted_posts_stay_out(self, cw):
        make_feed(cw["owner"], is_public=True)
        url = feed_url(cw["owner"], "my-feed", "posts/")
        HiddenPost.objects.create(user=cw["viewer"], post=cw["posts"]["py"])
        assert ids(client(cw["viewer"]).get(url)) == [cw["posts"]["js"].pk]
        # Hiding is per viewer.
        assert cw["posts"]["py"].pk in ids(client(cw["owner"]).get(url))
        Post.objects.filter(pk=cw["posts"]["js"].pk).update(is_nsfw=True)
        assert ids(client(cw["viewer"]).get(url)) == []
        User.objects.filter(pk=cw["viewer"].pk).update(show_nsfw=True)
        cw["viewer"].refresh_from_db()
        assert ids(client(cw["viewer"]).get(url)) == [cw["posts"]["js"].pk]
        Post.objects.filter(pk=cw["posts"]["js"].pk).update(is_approved=False)
        assert ids(client(cw["viewer"]).get(url)) == []
        Post.objects.filter(pk=cw["posts"]["js"].pk).update(
            is_approved=True, deleted_at=timezone.now()
        )
        assert ids(client(cw["viewer"]).get(url)) == []

    def test_nsfw_community_posts_follow_the_viewer_preference(self, cw):
        Community.objects.filter(pk=cw["js"].pk).update(is_nsfw=True)
        make_feed(cw["owner"], is_public=True)
        url = feed_url(cw["owner"], "my-feed", "posts/")
        assert ids(client().get(url)) == [cw["posts"]["py"].pk]

    def test_community_where_the_viewer_is_banned_produces_no_posts(self, cw):
        make_feed(cw["owner"], is_public=True)
        Membership.objects.create(
            user=cw["viewer"], community=cw["py"], role="member", is_banned=True
        )
        url = feed_url(cw["owner"], "my-feed", "posts/")
        assert ids(client(cw["viewer"]).get(url)) == [cw["posts"]["js"].pk]
        # The community stays listed on the feed itself.
        assert (
            "py" in client(cw["viewer"]).get(feed_url(cw["owner"], "my-feed")).data["communities"]
        )

    def test_deleting_a_community_drops_it_and_its_posts(self, cw):
        make_feed(cw["owner"], is_public=True)
        cw["js"].delete()
        assert client().get(feed_url(cw["owner"], "my-feed")).data["communities"] == ["py"]
        assert ids(client().get(feed_url(cw["owner"], "my-feed", "posts/"))) == [
            cw["posts"]["py"].pk
        ]

    def test_empty_feed_has_no_posts(self, cw):
        make_feed(cw["owner"], communities=[])
        assert ids(client(cw["owner"]).get(feed_url(cw["owner"], "my-feed", "posts/"))) == []

    def test_post_queries_do_not_grow_with_rows(self, cw):
        make_feed(cw["owner"], is_public=True)
        url = feed_url(cw["owner"], "my-feed", "posts/")
        api = client(cw["viewer"])
        with CaptureQueriesContext(connection) as small:
            api.get(url)
        for i in range(8):
            Post.objects.create(author=cw["author"], community=cw["py"], title=f"M{i}", body="b")
        with CaptureQueriesContext(connection) as large:
            response = api.get(url)
        assert len(response.data["results"]) == 10
        assert len(large) == len(small)

    def test_listing_queries_do_not_grow_with_feeds(self, cw):
        for i in range(2):
            make_feed(cw["owner"], name=f"F{i}", is_public=True)
        with CaptureQueriesContext(connection) as small:
            client(cw["viewer"]).get("/api/v1/users/owner/feeds/")
        for i in range(4):
            make_feed(cw["owner"], name=f"G{i}", is_public=True)
        with CaptureQueriesContext(connection) as large:
            client(cw["viewer"]).get("/api/v1/users/owner/feeds/")
        assert len(large) == len(small)


@pytest.mark.django_db
def test_export_and_account_deletion(cw):
    from apps.users.services import delete_account, export_account

    make_feed(cw["owner"], description="d", is_public=True)
    exported = export_account(cw["owner"])["custom_feeds"]
    assert exported == [
        {
            "name": "My Feed",
            "slug": "my-feed",
            "description": "d",
            "is_public": True,
            "communities": ["js", "py"],
        }
    ]
    delete_account(cw["owner"])
    assert CustomFeed.objects.filter(owner=cw["owner"]).count() == 0

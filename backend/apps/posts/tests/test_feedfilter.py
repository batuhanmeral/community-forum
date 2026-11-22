import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.communities.models import Community, Membership
from apps.posts.models import FeedExclusion, Post
from apps.social.models import Follow

User = get_user_model()


@pytest.fixture
def fw(db):
    owner = User.objects.create_user(username="owner", email="o@example.com")
    me = User.objects.create_user(username="me", email="me@example.com")
    other = User.objects.create_user(username="other", email="x@example.com")
    loud = Community.objects.create(slug="loud", name="Loud", creator=owner)
    calm = Community.objects.create(slug="calm", name="Calm", creator=owner)
    Membership.objects.create(user=me, community=loud, role="member")
    loud_post = Post.objects.create(author=owner, community=loud, title="Loud post", body="l")
    calm_post = Post.objects.create(author=owner, community=calm, title="Calm post", body="c")
    return {
        "owner": owner,
        "me": me,
        "other": other,
        "loud": loud,
        "calm": calm,
        "loud_post": loud_post,
        "calm_post": calm_post,
    }


def client(user=None):
    api = APIClient()
    if user:
        api.force_authenticate(user)
    return api


def exclude(user, community):
    return client(user).post(f"/api/v1/communities/{community.slug}/feed-exclusion/")


def ids(response):
    return [row["id"] for row in response.data["results"]]


@pytest.mark.django_db
class TestFeedExclusionEndpoints:
    def test_exclude_is_idempotent_and_state_readable(self, fw):
        api = client(fw["me"])
        url = f"/api/v1/communities/{fw['loud'].slug}/feed-exclusion/"
        assert api.get(url).data == {"excluded": False}
        assert api.post(url).status_code == 201
        assert api.post(url).status_code == 200
        assert api.get(url).data == {"excluded": True}
        assert FeedExclusion.objects.filter(user=fw["me"]).count() == 1
        assert api.delete(url).status_code == 204
        assert api.delete(url).status_code == 204
        assert api.get(url).data == {"excluded": False}

    def test_requires_login_and_existing_community(self, fw):
        assert exclude(None, fw["loud"]).status_code == 401
        assert client(fw["me"]).post("/api/v1/communities/nope/feed-exclusion/").status_code == 404

    def test_list_is_private_alphabetical_and_unpaginated(self, fw):
        exclude(fw["me"], fw["loud"])
        exclude(fw["me"], fw["calm"])
        rows = client(fw["me"]).get("/api/v1/users/me/feed-exclusions/").data
        assert [row["slug"] for row in rows] == ["calm", "loud"]
        assert client(fw["other"]).get("/api/v1/users/me/feed-exclusions/").data == []
        assert client().get("/api/v1/users/me/feed-exclusions/").status_code == 401

    def test_per_user_cap(self, fw, monkeypatch):
        monkeypatch.setattr("apps.posts.views.MAX_FEED_EXCLUSIONS", 2)
        extra = Community.objects.create(slug="extra", name="Extra", creator=fw["owner"])
        assert exclude(fw["me"], fw["loud"]).status_code == 201
        assert exclude(fw["me"], fw["calm"]).status_code == 201
        assert exclude(fw["me"], extra).status_code == 400
        # Re-excluding an existing one still works at the cap, and others have their own budget.
        assert exclude(fw["me"], fw["loud"]).status_code == 200
        assert exclude(fw["other"], extra).status_code == 201

    def test_deleting_the_community_removes_the_row(self, fw):
        exclude(fw["me"], fw["calm"])
        fw["calm"].delete()
        assert FeedExclusion.objects.count() == 0


@pytest.mark.django_db
class TestExcludedCommunitiesLeaveDiscoveryFeeds:
    def test_popular_and_all_drop_excluded_but_home_keeps_joined(self, fw):
        exclude(fw["me"], fw["loud"])
        exclude(fw["me"], fw["calm"])
        api = client(fw["me"])
        assert ids(api.get("/api/v1/feed/?scope=all")) == []
        # Home lists joined communities; excluding one does not touch it.
        assert ids(api.get("/api/v1/feed/")) == [fw["loud_post"].pk]

    def test_other_viewers_and_anonymous_are_unaffected(self, fw):
        exclude(fw["me"], fw["calm"])
        for api in (client(fw["other"]), client()):
            assert fw["calm_post"].pk in ids(api.get("/api/v1/feed/?scope=all"))
        assert ids(client().get("/api/v1/feed/")) and fw["calm_post"].pk in ids(
            client().get("/api/v1/feed/")
        )

    def test_following_and_community_pages_keep_excluded_posts(self, fw):
        exclude(fw["me"], fw["calm"])
        Follow.objects.create(follower=fw["me"], followed=fw["owner"])
        api = client(fw["me"])
        assert fw["calm_post"].pk in ids(api.get("/api/v1/feed/following/"))
        assert ids(api.get("/api/v1/communities/calm/posts/")) == [fw["calm_post"].pk]

    def test_trending_posts_and_communities(self, fw):
        exclude(fw["me"], fw["calm"])
        api = client(fw["me"])
        posts = api.get("/api/v1/trending/posts/")
        assert fw["calm_post"].pk not in ids(posts)
        assert fw["loud_post"].pk in ids(posts)
        communities = api.get("/api/v1/trending/communities/")
        slugs = [row["slug"] for row in communities.data["results"]]
        assert "calm" not in slugs and "loud" in slugs
        # force_authenticate sends no Authorization header, so the page cache would be shared.
        cache.clear()
        anon = [
            row["slug"] for row in client().get("/api/v1/trending/communities/").data["results"]
        ]
        assert "calm" in anon

    def test_notification_level_is_separate(self, fw):
        Membership.objects.filter(user=fw["me"], community=fw["loud"]).update(notify_level="off")
        assert exclude(fw["me"], fw["loud"]).status_code == 201
        membership = Membership.objects.get(user=fw["me"], community=fw["loud"])
        assert membership.notify_level == "off"
        exclude_row = FeedExclusion.objects.get(user=fw["me"], community=fw["loud"])
        assert exclude_row.pk
        client(fw["me"]).delete("/api/v1/communities/loud/feed-exclusion/")
        membership.refresh_from_db()
        assert membership.notify_level == "off"

    def test_filter_adds_no_per_row_queries(self, fw):
        api = client(fw["me"])
        exclude(fw["me"], fw["calm"])
        with CaptureQueriesContext(connection) as small:
            api.get("/api/v1/feed/?scope=all")
        for i in range(4):
            community = Community.objects.create(slug=f"k{i}", name=f"K{i}", creator=fw["owner"])
            Post.objects.create(author=fw["owner"], community=community, title=f"K{i}")
            if i % 2:
                exclude(fw["me"], community)
        with CaptureQueriesContext(connection) as large:
            response = api.get("/api/v1/feed/?scope=all")
        assert len(response.data["results"]) == 3  # loud post + two kept communities
        assert len(large) == len(small)


@pytest.mark.django_db
def test_export_and_account_deletion(fw):
    from apps.users.services import delete_account, export_account

    exclude(fw["me"], fw["calm"])
    assert export_account(fw["me"])["feed_exclusions"] == ["calm"]
    delete_account(fw["me"])
    assert FeedExclusion.objects.filter(user=fw["me"]).count() == 0

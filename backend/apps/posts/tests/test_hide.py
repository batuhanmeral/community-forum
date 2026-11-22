import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.communities.models import Community, Membership
from apps.posts.models import HiddenPost, Post
from apps.social.models import Follow

User = get_user_model()


@pytest.fixture
def hw(db):
    owner = User.objects.create_user(username="owner", email="o@example.com")
    me = User.objects.create_user(username="me", email="me@example.com")
    other = User.objects.create_user(username="other", email="x@example.com")
    community = Community.objects.create(slug="c1", name="C1", creator=owner)
    Membership.objects.create(user=me, community=community, role="member")
    keep = Post.objects.create(author=owner, community=community, title="Keep", body="k")
    gone = Post.objects.create(author=owner, community=community, title="Gone", body="g")
    return {
        "owner": owner,
        "me": me,
        "other": other,
        "community": community,
        "keep": keep,
        "gone": gone,
    }


def client(user=None):
    api = APIClient()
    if user:
        api.force_authenticate(user)
    return api


def hide(user, post):
    return client(user).post(f"/api/v1/posts/{post.pk}/hide/")


def ids(response):
    return [row["id"] for row in response.data["results"]]


@pytest.mark.django_db
class TestHideEndpoints:
    def test_hide_is_idempotent_and_unhide_works(self, hw):
        assert hide(hw["me"], hw["gone"]).status_code == 201
        assert hide(hw["me"], hw["gone"]).status_code == 200
        assert HiddenPost.objects.filter(user=hw["me"]).count() == 1
        api = client(hw["me"])
        assert api.delete(f"/api/v1/posts/{hw['gone'].pk}/hide/").status_code == 204
        assert api.delete(f"/api/v1/posts/{hw['gone'].pk}/hide/").status_code == 204
        assert HiddenPost.objects.count() == 0

    def test_requires_login(self, hw):
        assert hide(None, hw["gone"]).status_code == 401
        assert client().get("/api/v1/users/me/hidden/").status_code == 401

    def test_cannot_hide_unknown_held_or_deleted_posts(self, hw):
        assert client(hw["me"]).post("/api/v1/posts/99999/hide/").status_code == 404
        Post.objects.filter(pk=hw["gone"].pk).update(is_approved=False)
        assert hide(hw["me"], hw["gone"]).status_code == 404
        Post.objects.filter(pk=hw["gone"].pk).update(is_approved=True, deleted_at=timezone.now())
        assert hide(hw["me"], hw["gone"]).status_code == 404

    def test_hidden_list_is_private_and_newest_first(self, hw):
        hide(hw["me"], hw["keep"])
        hide(hw["me"], hw["gone"])
        assert ids(client(hw["me"]).get("/api/v1/users/me/hidden/")) == [
            hw["gone"].pk,
            hw["keep"].pk,
        ]
        assert ids(client(hw["other"]).get("/api/v1/users/me/hidden/")) == []

    def test_hidden_list_drops_deleted_and_nsfw_posts(self, hw):
        hide(hw["me"], hw["keep"])
        hide(hw["me"], hw["gone"])
        Post.objects.filter(pk=hw["gone"].pk).update(deleted_at=timezone.now())
        assert ids(client(hw["me"]).get("/api/v1/users/me/hidden/")) == [hw["keep"].pk]
        Post.objects.filter(pk=hw["keep"].pk).update(is_nsfw=True)
        assert ids(client(hw["me"]).get("/api/v1/users/me/hidden/")) == []
        User.objects.filter(pk=hw["me"].pk).update(show_nsfw=True)
        hw["me"].refresh_from_db()
        assert ids(client(hw["me"]).get("/api/v1/users/me/hidden/")) == [hw["keep"].pk]

    def test_per_user_cap_prunes_the_oldest(self, hw, monkeypatch):
        monkeypatch.setattr("apps.posts.views.MAX_HIDDEN_PER_USER", 3)
        posts = [
            Post.objects.create(author=hw["owner"], community=hw["community"], title=f"P{i}")
            for i in range(5)
        ]
        for post in posts:
            assert hide(hw["me"], post).status_code == 201
        kept = set(HiddenPost.objects.filter(user=hw["me"]).values_list("post_id", flat=True))
        assert kept == {p.pk for p in posts[2:]}
        # Another user's list is untouched by the cap.
        hide(hw["other"], posts[0])
        assert HiddenPost.objects.filter(user=hw["other"]).count() == 1

    def test_prune_under_the_cap_only_counts(self, hw):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from apps.posts.views import _prune_hidden

        HiddenPost.objects.create(user=hw["me"], post=hw["keep"])
        with CaptureQueriesContext(connection) as ctx:
            _prune_hidden(hw["me"])
        sql = [q["sql"] for q in ctx.captured_queries]
        assert len(sql) == 1 and "COUNT(" in sql[0], sql

    def test_deleting_the_post_removes_the_row(self, hw):
        hide(hw["me"], hw["gone"])
        hw["gone"].delete()
        assert HiddenPost.objects.count() == 0


@pytest.mark.django_db
class TestHiddenPostsLeaveFeeds:
    def setup_hidden(self, hw):
        assert hide(hw["me"], hw["gone"]).status_code == 201

    def test_community_feed_all_and_home(self, hw):
        self.setup_hidden(hw)
        api = client(hw["me"])
        for url in (
            "/api/v1/communities/c1/posts/",
            "/api/v1/feed/",
            "/api/v1/feed/?scope=all",
        ):
            assert ids(api.get(url)) == [hw["keep"].pk], url

    def test_following_feed(self, hw):
        Follow.objects.create(follower=hw["me"], followed=hw["owner"])
        self.setup_hidden(hw)
        assert ids(client(hw["me"]).get("/api/v1/feed/following/")) == [hw["keep"].pk]

    def test_search(self, hw):
        Post.objects.filter(pk__in=[hw["keep"].pk, hw["gone"].pk]).update(
            title="needle", body="needle"
        )
        from django.contrib.postgres.search import SearchVector

        Post.objects.update(search_vector=SearchVector("title", "body"))
        self.setup_hidden(hw)
        response = client(hw["me"]).get("/api/v1/search/?q=needle&type=post")
        assert ids(response) == [hw["keep"].pk]

    def test_trending_posts(self, hw):
        self.setup_hidden(hw)
        response = client(hw["me"]).get("/api/v1/trending/posts/")
        assert hw["gone"].pk not in ids(response)
        assert hw["keep"].pk in ids(response)

    def test_exemptions_profile_direct_link_and_other_viewers(self, hw):
        self.setup_hidden(hw)
        api = client(hw["me"])
        assert hw["gone"].pk in ids(api.get("/api/v1/users/owner/posts/"))
        assert api.get(f"/api/v1/posts/{hw['gone'].pk}/").status_code == 200
        assert hw["gone"].pk in ids(client(hw["other"]).get("/api/v1/feed/?scope=all"))
        assert hw["gone"].pk in ids(client().get("/api/v1/feed/"))

    def test_hidden_filter_adds_no_per_row_queries(self, hw):
        api = client(hw["me"])
        with CaptureQueriesContext(connection) as small:
            api.get("/api/v1/feed/?scope=all")
        for i in range(6):
            post = Post.objects.create(author=hw["owner"], community=hw["community"], title=f"M{i}")
            if i % 2:
                hide(hw["me"], post)
        with CaptureQueriesContext(connection) as large:
            response = api.get("/api/v1/feed/?scope=all")
        assert len(response.data["results"]) == 5
        assert len(large) == len(small)


@pytest.mark.django_db
class TestHiddenAndAccount:
    def test_export_lists_hidden_and_deletion_clears_it(self, hw):
        from apps.users.services import delete_account, export_account

        hide(hw["me"], hw["gone"])
        assert export_account(hw["me"])["hidden"] == [{"post_id": hw["gone"].pk}]
        delete_account(hw["me"])
        assert HiddenPost.objects.filter(user=hw["me"]).count() == 0

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.communities.models import Community, Membership
from apps.moderation.models import ModAction
from apps.posts.models import Post

User = get_user_model()


def log_url(slug):
    return reverse("api_v1:moderation:community-mod-log", args=[slug])


def ban_url(slug, username):
    return reverse("api_v1:moderation:community-mod-ban", args=[slug, username])


def sticky_url(pk):
    return reverse("api_v1:posts:post-sticky", args=[pk])


def community_posts_url(slug):
    return reverse("api_v1:community-posts:community-posts", args=[slug])


def community_detail_url(slug):
    return reverse("api_v1:communities:community-detail", args=[slug])


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
def community(alice):
    return Community.objects.create(slug="py", name="Python", creator=alice)


@pytest.fixture
def member(community, bob):
    Membership.objects.create(user=bob, community=community, role=Membership.Role.MEMBER)
    return bob


@pytest.mark.django_db
class TestModLog:
    def test_ban_is_logged(self, api, community, alice, member):
        api.force_authenticate(alice)
        api.post(ban_url("py", "bob"))
        entry = ModAction.objects.get(community=community, action=ModAction.Action.USER_BAN)
        assert entry.actor == alice
        assert entry.object_id == member.id

    def test_unban_is_logged(self, api, community, alice, member):
        api.force_authenticate(alice)
        api.post(ban_url("py", "bob"))
        api.delete(ban_url("py", "bob"))
        assert ModAction.objects.filter(
            community=community, action=ModAction.Action.USER_UNBAN
        ).exists()

    def test_pin_is_logged(self, api, community, alice):
        post = Post.objects.create(author=alice, community=community, kind="text", title="t")
        api.force_authenticate(alice)
        api.post(sticky_url(post.pk))
        assert ModAction.objects.filter(
            community=community, action=ModAction.Action.POST_PIN, object_id=post.pk
        ).exists()

    def test_log_endpoint_mod_only(self, api, community, alice, member):
        api.force_authenticate(member)
        assert api.get(log_url("py")).status_code == 403
        api.force_authenticate(alice)
        resp = api.get(log_url("py"))
        assert resp.status_code == 200

    def test_log_entries_serialized(self, api, community, alice, member):
        api.force_authenticate(alice)
        api.post(ban_url("py", "bob"))
        resp = api.get(log_url("py"))
        entry = resp.data["results"][0]
        assert entry["action"] == "user_ban"
        assert entry["actor_username"] == "alice"
        assert entry["target_type"] == "user"


@pytest.mark.django_db
class TestAutoMod:
    @pytest.fixture
    def strict_community(self, alice):
        return Community.objects.create(
            slug="strict",
            name="Strict",
            creator=alice,
            banned_keywords="crypto scam\nspammy",
        )

    def _post(self, api, title="hello", body=""):
        return api.post(
            community_posts_url("strict"),
            {"kind": "text", "title": title, "body": body},
            format="json",
        )

    def test_matching_post_is_held(self, api, strict_community, bob):
        Membership.objects.create(user=bob, community=strict_community)
        api.force_authenticate(bob)
        resp = self._post(api, title="Great CRYPTO SCAM opportunity")
        assert resp.status_code == 201
        post = Post.objects.get(pk=resp.data["id"])
        assert post.is_approved is False
        entry = ModAction.objects.get(action=ModAction.Action.AUTOMOD_HOLD)
        assert entry.actor is None
        assert "crypto scam" in entry.detail

    def test_body_is_checked_too(self, api, strict_community, bob):
        Membership.objects.create(user=bob, community=strict_community)
        api.force_authenticate(bob)
        resp = self._post(api, title="innocent", body="totally spammy content")
        assert Post.objects.get(pk=resp.data["id"]).is_approved is False

    def test_clean_post_passes(self, api, strict_community, bob):
        Membership.objects.create(user=bob, community=strict_community)
        api.force_authenticate(bob)
        resp = self._post(api, title="A normal post")
        assert Post.objects.get(pk=resp.data["id"]).is_approved is True

    def test_moderator_bypasses_automod(self, api, strict_community, alice):
        api.force_authenticate(alice)
        resp = self._post(api, title="crypto scam awareness thread")
        assert Post.objects.get(pk=resp.data["id"]).is_approved is True


@pytest.mark.django_db
class TestBannedKeywordsVisibility:
    def test_hidden_from_non_mods(self, api, community, member):
        api.force_authenticate(member)
        resp = api.get(community_detail_url("py"))
        assert "banned_keywords" not in resp.data

    def test_hidden_from_anonymous(self, api, community):
        resp = api.get(community_detail_url("py"))
        assert "banned_keywords" not in resp.data

    def test_visible_to_admin(self, api, community, alice):
        api.force_authenticate(alice)
        resp = api.get(community_detail_url("py"))
        assert "banned_keywords" in resp.data

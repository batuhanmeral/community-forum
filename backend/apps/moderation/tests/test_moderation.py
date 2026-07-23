import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.comments.models import Comment
from apps.communities.models import Community, Membership
from apps.moderation.models import Report
from apps.notifications.models import Notification
from apps.posts.models import Post

User = get_user_model()
REPORT_URL = reverse("api_v1:moderation:report-create")


def queue(slug):
    return reverse("api_v1:moderation:community-mod-reports", args=[slug])


def resolve_url(slug, pk):
    return reverse("api_v1:moderation:community-mod-report-resolve", args=[slug, pk])


def dismiss_url(slug, pk):
    return reverse("api_v1:moderation:community-mod-report-dismiss", args=[slug, pk])


def ban_url(slug, username):
    return reverse("api_v1:moderation:community-mod-ban", args=[slug, username])


def role_url(slug, username):
    return reverse("api_v1:moderation:community-mod-member", args=[slug, username])


def post_detail(pk):
    return reverse("api_v1:posts:post-detail", args=[pk])


def comment_detail(pk):
    return reverse("api_v1:comments:comment-detail", args=[pk])


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
def community(alice):
    return Community.objects.create(slug="py", name="Python", creator=alice)


@pytest.fixture
def mod(community, bob):
    Membership.objects.create(user=bob, community=community, role=Membership.Role.MODERATOR)
    return bob


@pytest.fixture
def post(alice, community):
    return Post.objects.create(author=alice, community=community, kind="text", title="t")


@pytest.fixture
def comment(post, alice):
    return Comment.objects.create(post=post, author=alice, body="hi")


@pytest.mark.django_db
class TestReportCreate:
    def test_anonymous_rejected(self, api, post):
        assert (
            api.post(
                REPORT_URL, {"content_type": "post", "object_id": post.id, "reason": "x"}
            ).status_code
            == 401
        )

    def test_create_report(self, api, carol, post):
        api.force_authenticate(carol)
        resp = api.post(
            REPORT_URL,
            {"content_type": "post", "object_id": post.id, "reason": "spam"},
            format="json",
        )
        assert resp.status_code == 201
        assert Report.objects.count() == 1

    def test_duplicate_within_24h_rejected(self, api, carol, post):
        api.force_authenticate(carol)
        api.post(
            REPORT_URL,
            {"content_type": "post", "object_id": post.id, "reason": "spam"},
            format="json",
        )
        resp = api.post(
            REPORT_URL,
            {"content_type": "post", "object_id": post.id, "reason": "spam"},
            format="json",
        )
        assert resp.status_code == 400

    def test_unknown_target_400(self, api, carol):
        api.force_authenticate(carol)
        resp = api.post(
            REPORT_URL, {"content_type": "post", "object_id": 9999, "reason": "x"}, format="json"
        )
        assert resp.status_code == 400

    def test_user_target_supported(self, api, carol, bob):
        api.force_authenticate(carol)
        resp = api.post(
            REPORT_URL,
            {"content_type": "user", "object_id": bob.id, "reason": "harassment"},
            format="json",
        )
        assert resp.status_code == 201


@pytest.mark.django_db
class TestModQueue:
    def test_non_mod_cannot_see(self, api, carol, community):
        api.force_authenticate(carol)
        assert api.get(queue("py")).status_code == 403

    def test_mod_sees_only_community_reports(self, api, mod, post, carol, community):
        other = Community.objects.create(slug="rust", name="Rust", creator=carol)
        other_post = Post.objects.create(author=carol, community=other, kind="text", title="o")
        # report inside py
        api.force_authenticate(carol)
        api.post(
            REPORT_URL,
            {"content_type": "post", "object_id": post.id, "reason": "spam"},
            format="json",
        )
        # report outside py
        api.post(
            REPORT_URL,
            {"content_type": "post", "object_id": other_post.id, "reason": "spam"},
            format="json",
        )
        api.force_authenticate(mod)
        resp = api.get(queue("py"))
        assert resp.data["count"] == 1
        assert resp.data["results"][0]["object_id"] == post.id

    def test_status_filter(self, api, mod, post, carol):
        api.force_authenticate(carol)
        api.post(
            REPORT_URL, {"content_type": "post", "object_id": post.id, "reason": "x"}, format="json"
        )
        api.force_authenticate(mod)
        resp = api.get(queue("py"), {"status": "open"})
        assert resp.data["count"] == 1
        resp = api.get(queue("py"), {"status": "resolved"})
        assert resp.data["count"] == 0


@pytest.mark.django_db
class TestResolveDismiss:
    def _report(self, api, carol, target):
        api.force_authenticate(carol)
        api.post(
            REPORT_URL,
            {
                "content_type": target.__class__.__name__.lower(),
                "object_id": target.id,
                "reason": "x",
            },
            format="json",
        )
        return Report.objects.get()

    def test_resolve_notifies_target_author(self, api, mod, post, carol, alice):
        report = self._report(api, carol, post)
        api.force_authenticate(mod)
        resp = api.post(resolve_url("py", report.id))
        assert resp.status_code == 200
        report.refresh_from_db()
        assert report.status == "resolved"
        assert Notification.objects.filter(recipient=alice, verb="mod_action").exists()

    def test_dismiss_does_not_notify(self, api, mod, post, carol, alice):
        report = self._report(api, carol, post)
        api.force_authenticate(mod)
        api.post(dismiss_url("py", report.id))
        report.refresh_from_db()
        assert report.status == "dismissed"
        assert not Notification.objects.filter(recipient=alice, verb="mod_action").exists()

    def test_cannot_resolve_report_from_other_community(self, api, mod, carol, alice):
        other = Community.objects.create(slug="rust", name="Rust", creator=alice)
        other_post = Post.objects.create(author=alice, community=other, kind="text", title="o")
        report = self._report(api, carol, other_post)
        api.force_authenticate(mod)
        resp = api.post(resolve_url("py", report.id))
        assert resp.status_code == 404


@pytest.mark.django_db
class TestModDelete:
    def test_mod_can_delete_post(self, api, mod, post, alice):
        api.force_authenticate(mod)
        resp = api.delete(post_detail(post.id))
        assert resp.status_code == 204
        post.refresh_from_db()
        assert post.deleted_at is not None and post.deleted_by == mod
        assert Notification.objects.filter(recipient=alice, verb="mod_action").exists()

    def test_mod_can_delete_comment(self, api, mod, comment, alice):
        api.force_authenticate(mod)
        assert api.delete(comment_detail(comment.id)).status_code == 204
        assert Notification.objects.filter(recipient=alice, verb="mod_action").exists()

    def test_regular_user_cannot_delete_others_post(self, api, carol, post):
        api.force_authenticate(carol)
        assert api.delete(post_detail(post.id)).status_code == 403


@pytest.mark.django_db
class TestBan:
    def test_mod_bans_user(self, api, mod, carol, community):
        Membership.objects.create(user=carol, community=community)
        api.force_authenticate(mod)
        resp = api.post(ban_url("py", "carol"))
        assert resp.status_code == 200
        assert Membership.objects.get(user=carol, community=community).is_banned is True
        assert Notification.objects.filter(recipient=carol, verb="mod_action").exists()

    def test_banned_user_cannot_rejoin(self, api, mod, carol):
        api.force_authenticate(mod)
        api.post(ban_url("py", "carol"))
        api.force_authenticate(carol)
        membership_url = reverse("api_v1:communities:community-membership", args=["py"])
        resp = api.post(membership_url)
        assert resp.status_code == 400

    def test_banned_user_cannot_post(self, api, mod, carol):
        Membership.objects.create(user=carol, community=Community.objects.get(slug="py"))
        api.force_authenticate(mod)
        api.post(ban_url("py", "carol"))
        api.force_authenticate(carol)
        url = reverse("api_v1:community-posts:community-posts", args=["py"])
        resp = api.post(url, {"title": "x", "kind": "text"}, format="json")
        assert resp.status_code == 403

    def test_cannot_ban_creator(self, api, mod, alice):
        api.force_authenticate(mod)
        assert api.post(ban_url("py", "alice")).status_code == 400

    def test_unban(self, api, mod, carol, community):
        Membership.objects.create(user=carol, community=community, is_banned=True)
        api.force_authenticate(mod)
        resp = api.delete(ban_url("py", "carol"))
        assert resp.status_code == 204
        assert Membership.objects.get(user=carol).is_banned is False


@pytest.mark.django_db
class TestRoleUpdate:
    def test_admin_promotes_to_moderator(self, api, alice, carol, community):
        Membership.objects.create(user=carol, community=community)
        api.force_authenticate(alice)
        resp = api.patch(role_url("py", "carol"), {"role": "moderator"}, format="json")
        assert resp.status_code == 200
        assert Membership.objects.get(user=carol).role == "moderator"

    def test_mod_cannot_promote(self, api, mod, carol, community):
        Membership.objects.create(user=carol, community=community)
        api.force_authenticate(mod)
        resp = api.patch(role_url("py", "carol"), {"role": "moderator"}, format="json")
        assert resp.status_code == 403

    def test_cannot_demote_creator(self, api, alice, community):
        api.force_authenticate(alice)
        resp = api.patch(role_url("py", "alice"), {"role": "member"}, format="json")
        assert resp.status_code == 400

    def test_invalid_role_rejected(self, api, alice, carol, community):
        Membership.objects.create(user=carol, community=community)
        api.force_authenticate(alice)
        resp = api.patch(role_url("py", "carol"), {"role": "god"}, format="json")
        assert resp.status_code == 400

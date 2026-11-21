import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.communities.models import Community, Membership
from apps.posts.models import Post

User = get_user_model()


def ban_url(slug, username):
    return reverse("api_v1:moderation:community-mod-ban", args=[slug, username])


def role_url(slug, username):
    return reverse("api_v1:moderation:community-mod-member", args=[slug, username])


def sticky_url(pk):
    return reverse("api_v1:posts:post-sticky", args=[pk])


def _user(name):
    return User.objects.create_user(username=name, email=f"{name}@x.com", password="StrongPass123!")


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def creator(db):
    return _user("creator")


@pytest.fixture
def community(creator):
    return Community.objects.create(slug="py", name="Py", creator=creator)


@pytest.fixture
def staff(community):
    """One admin, two moderators and a member besides the creator."""
    users = {}
    for name, role in (
        ("adm", Membership.Role.ADMIN),
        ("mod", Membership.Role.MODERATOR),
        ("mod2", Membership.Role.MODERATOR),
        ("mem", Membership.Role.MEMBER),
    ):
        users[name] = _user(name)
        Membership.objects.create(user=users[name], community=community, role=role)
    return users


@pytest.mark.django_db
class TestBanHierarchy:
    def test_moderator_cannot_ban_admin(self, api, community, staff):
        api.force_authenticate(staff["mod"])
        assert api.post(ban_url("py", "adm")).status_code == 403
        membership = Membership.objects.get(user=staff["adm"], community=community)
        assert membership.role == Membership.Role.ADMIN
        assert membership.is_banned is False

    @pytest.mark.parametrize(
        "actor, target, status",
        [
            pytest.param("mod", "mod2", 403, id="moderator-bans-peer"),
            pytest.param("mod", "mem", 200, id="moderator-bans-member"),
            pytest.param("adm", "mod", 200, id="admin-bans-moderator"),
        ],
    )
    def test_ban_permission_by_rank(self, api, staff, actor, target, status):
        api.force_authenticate(staff[actor])
        assert api.post(ban_url("py", target)).status_code == status


@pytest.mark.django_db
class TestRoleHierarchy:
    def test_admin_cannot_demote_other_admin(self, api, community, creator, staff):
        other_admin = _user("adm2")
        Membership.objects.create(user=other_admin, community=community, role=Membership.Role.ADMIN)
        api.force_authenticate(staff["adm"])
        resp = api.patch(role_url("py", "adm2"), {"role": "member"}, format="json")
        assert resp.status_code == 403


@pytest.mark.django_db
class TestBannedModerator:
    def test_banned_moderator_cannot_pin(self, api, community, creator, staff):
        Membership.objects.filter(user=staff["mod"], community=community).update(is_banned=True)
        post = Post.objects.create(author=creator, community=community, title="t")
        api.force_authenticate(staff["mod"])
        assert api.post(sticky_url(post.id)).status_code == 403


@pytest.mark.django_db
class TestRoleAssignment:
    @pytest.mark.parametrize(
        "actor, target, role, status",
        [
            pytest.param("adm", "mem", "admin", 403, id="admin-promotes-to-admin"),
            pytest.param("adm", "mem", "moderator", 200, id="admin-promotes-to-moderator"),
            pytest.param("creator", "mem", "admin", 200, id="creator-promotes-to-admin"),
            pytest.param("creator", "adm", "moderator", 200, id="creator-demotes-admin"),
        ],
    )
    def test_role_change_permission_by_rank(self, api, creator, staff, actor, target, role, status):
        api.force_authenticate(creator if actor == "creator" else staff[actor])
        resp = api.patch(role_url("py", target), {"role": role}, format="json")
        assert resp.status_code == status

    def test_role_change_on_banned_membership_rejected(self, api, community, staff):
        Membership.objects.filter(user=staff["mem"], community=community).update(is_banned=True)
        api.force_authenticate(staff["adm"])
        resp = api.patch(role_url("py", "mem"), {"role": "moderator"}, format="json")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestUnbanHierarchy:
    def test_moderator_cannot_unban_moderator_row(self, api, community, staff):
        victim = _user("victim")
        Membership.objects.create(
            user=victim, community=community, role=Membership.Role.MODERATOR, is_banned=True
        )
        api.force_authenticate(staff["mod"])
        assert api.delete(ban_url("py", "victim")).status_code == 403
        assert Membership.objects.get(user=victim, community=community).is_banned is True

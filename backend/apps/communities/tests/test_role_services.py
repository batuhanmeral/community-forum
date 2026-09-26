import pytest
from django.contrib.auth import get_user_model

from apps.communities.models import Community, Membership
from apps.communities.services import (
    can_assign_role,
    can_moderate_member,
    is_banned,
    is_moderator,
)

User = get_user_model()


def _user(name):
    return User.objects.create_user(username=name, email=f"{name}@x.com", password="StrongPass123!")


def _member(community, name, role=Membership.Role.MEMBER, banned=False):
    user = _user(name)
    Membership.objects.create(user=user, community=community, role=role, is_banned=banned)
    return user


@pytest.fixture
def creator(db):
    return _user("creator")


@pytest.fixture
def community(creator):
    return Community.objects.create(slug="py", name="Py", creator=creator)


@pytest.mark.django_db
class TestIsModerator:
    def test_admin_and_moderator_count(self, community):
        assert is_moderator(_member(community, "mod", Membership.Role.MODERATOR), community)
        assert is_moderator(_member(community, "adm", Membership.Role.ADMIN), community)

    def test_member_and_anonymous_do_not(self, community):
        from django.contrib.auth.models import AnonymousUser

        assert not is_moderator(_member(community, "mem"), community)
        assert not is_moderator(AnonymousUser(), community)

    def test_banned_moderator_loses_powers(self, community):
        banned_mod = _member(community, "bm", Membership.Role.MODERATOR, banned=True)
        assert not is_moderator(banned_mod, community)
        assert is_banned(banned_mod, community)


@pytest.mark.django_db
class TestCanModerateMember:
    def test_moderator_acts_on_member(self, community):
        mod = _member(community, "mod", Membership.Role.MODERATOR)
        assert can_moderate_member(mod, _member(community, "mem"), community)

    def test_non_member_target_counts_as_member(self, community):
        mod = _member(community, "mod", Membership.Role.MODERATOR)
        assert can_moderate_member(mod, _user("outsider"), community)

    def test_moderator_cannot_act_on_peers_or_admins(self, community):
        mod = _member(community, "mod", Membership.Role.MODERATOR)
        peer = _member(community, "mod2", Membership.Role.MODERATOR)
        admin = _member(community, "adm", Membership.Role.ADMIN)
        assert not can_moderate_member(mod, peer, community)
        assert not can_moderate_member(mod, admin, community)

    def test_admin_cannot_act_on_admin_but_creator_can(self, creator, community):
        admin = _member(community, "adm", Membership.Role.ADMIN)
        other_admin = _member(community, "adm2", Membership.Role.ADMIN)
        assert not can_moderate_member(admin, other_admin, community)
        assert can_moderate_member(creator, other_admin, community)

    def test_nobody_acts_on_creator(self, creator, community):
        admin = _member(community, "adm", Membership.Role.ADMIN)
        assert not can_moderate_member(admin, creator, community)

    def test_member_cannot_act(self, community):
        member = _member(community, "mem")
        assert not can_moderate_member(member, _member(community, "mem2"), community)


@pytest.mark.django_db
class TestCanAssignRole:
    def test_admin_assigns_moderator_not_admin(self, community):
        admin = _member(community, "adm", Membership.Role.ADMIN)
        assert can_assign_role(admin, community, Membership.Role.MODERATOR)
        assert not can_assign_role(admin, community, Membership.Role.ADMIN)

    def test_moderator_cannot_assign_mod_roles(self, community):
        mod = _member(community, "mod", Membership.Role.MODERATOR)
        for role in (Membership.Role.MODERATOR, Membership.Role.ADMIN):
            assert not can_assign_role(mod, community, role)

    def test_creator_assigns_admin(self, creator, community):
        Membership.objects.filter(user=creator, community=community).update(
            role=Membership.Role.ADMIN
        )
        assert can_assign_role(creator, community, Membership.Role.ADMIN)

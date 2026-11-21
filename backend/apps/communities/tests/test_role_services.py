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
    @pytest.mark.parametrize(
        "actor_role, target_role, expected",
        [
            pytest.param(
                Membership.Role.MODERATOR, Membership.Role.MEMBER, True, id="moderator-on-member"
            ),
            pytest.param(
                Membership.Role.MODERATOR,
                Membership.Role.MODERATOR,
                False,
                id="moderator-on-moderator",
            ),
            pytest.param(
                Membership.Role.MODERATOR, Membership.Role.ADMIN, False, id="moderator-on-admin"
            ),
            pytest.param(
                Membership.Role.MEMBER, Membership.Role.MEMBER, False, id="member-on-member"
            ),
        ],
    )
    def test_can_moderate_member_by_rank(self, community, actor_role, target_role, expected):
        actor = _member(community, "actor", actor_role)
        target = _member(community, "target", target_role)
        assert can_moderate_member(actor, target, community) is expected

    def test_non_member_target_counts_as_member(self, community):
        mod = _member(community, "mod", Membership.Role.MODERATOR)
        assert can_moderate_member(mod, _user("outsider"), community)

    def test_admin_cannot_act_on_admin_but_creator_can(self, creator, community):
        admin = _member(community, "adm", Membership.Role.ADMIN)
        other_admin = _member(community, "adm2", Membership.Role.ADMIN)
        assert not can_moderate_member(admin, other_admin, community)
        assert can_moderate_member(creator, other_admin, community)

    def test_nobody_acts_on_creator(self, creator, community):
        admin = _member(community, "adm", Membership.Role.ADMIN)
        assert not can_moderate_member(admin, creator, community)


@pytest.mark.django_db
class TestCanAssignRole:
    @pytest.mark.parametrize(
        "actor_role, new_role, expected",
        [
            pytest.param(
                Membership.Role.ADMIN, Membership.Role.MODERATOR, True, id="admin-assigns-moderator"
            ),
            pytest.param(
                Membership.Role.ADMIN, Membership.Role.ADMIN, False, id="admin-assigns-admin"
            ),
            pytest.param(
                Membership.Role.MODERATOR,
                Membership.Role.MODERATOR,
                False,
                id="moderator-assigns-moderator",
            ),
            pytest.param(
                Membership.Role.MODERATOR,
                Membership.Role.ADMIN,
                False,
                id="moderator-assigns-admin",
            ),
        ],
    )
    def test_can_assign_role_by_rank(self, community, actor_role, new_role, expected):
        actor = _member(community, "actor", actor_role)
        assert can_assign_role(actor, community, new_role) is expected

    def test_creator_assigns_admin(self, creator, community):
        Membership.objects.filter(user=creator, community=community).update(
            role=Membership.Role.ADMIN
        )
        assert can_assign_role(creator, community, Membership.Role.ADMIN)

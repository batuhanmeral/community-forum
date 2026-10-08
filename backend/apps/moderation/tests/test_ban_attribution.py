from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.communities.models import Community, Membership
from apps.moderation.models import ModAction
from apps.moderation.views import CommunityBanView
from apps.notifications.models import Notification

User = get_user_model()


def ban_url(slug, username):
    return reverse("api_v1:moderation:community-mod-ban", args=[slug, username])


def _user(name):
    return User.objects.create_user(username=name, email=f"{name}@x.com", password="x")


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


def _ban(api, actor, username="mem"):
    api.force_authenticate(actor)
    return api.post(ban_url("py", username))


def _unban(api, actor, username="mem"):
    api.force_authenticate(actor)
    return api.delete(ban_url("py", username))


def _membership(community, user):
    return Membership.objects.get(community=community, user=user)


@pytest.mark.django_db
class TestBanAttribution:
    def test_ban_records_issuer_and_time(self, api, community, staff):
        _ban(api, staff["mod"])
        m = _membership(community, staff["mem"])
        assert m.banned_by == staff["mod"]
        assert m.banned_at is not None

    def test_moderator_cannot_lift_an_admin_ban(self, api, community, staff):
        _ban(api, staff["adm"])
        assert _unban(api, staff["mod"]).status_code == 403
        assert _membership(community, staff["mem"]).is_banned is True

    def test_peer_moderator_can_lift_a_moderator_ban(self, api, community, staff):
        _ban(api, staff["mod"])
        assert _unban(api, staff["mod2"]).status_code == 204
        assert _membership(community, staff["mem"]).is_banned is False

    def test_admin_lifts_a_moderator_ban_and_clears_the_issuer(self, api, community, staff):
        _ban(api, staff["mod"])
        assert _unban(api, staff["adm"]).status_code == 204
        m = _membership(community, staff["mem"])
        assert (m.is_banned, m.banned_by, m.banned_at) == (False, None, None)

    def test_only_the_creator_lifts_a_creator_ban(self, api, community, creator, staff):
        _ban(api, creator)
        assert _unban(api, staff["adm"]).status_code == 403
        assert _unban(api, creator).status_code == 204

    def test_demoted_issuer_no_longer_protects_the_ban(self, api, community, staff):
        _ban(api, staff["adm"])
        Membership.objects.filter(user=staff["adm"], community=community).update(
            role=Membership.Role.MEMBER
        )
        assert _unban(api, staff["mod"]).status_code == 204

    def test_reban_keeps_the_original_issuer(self, api, community, staff):
        _ban(api, staff["adm"])
        assert _ban(api, staff["mod"]).status_code == 200
        assert _membership(community, staff["mem"]).banned_by == staff["adm"]
        assert ModAction.objects.filter(action=ModAction.Action.USER_BAN).count() == 1
        assert _unban(api, staff["mod"]).status_code == 403

    def test_concurrent_bans_keep_the_first_issuer(self, api, community, staff):
        mem = staff["mem"]
        snapshots = [_membership(community, mem), _membership(community, mem)]
        with patch.object(
            Membership.objects,
            "get_or_create",
            side_effect=[(snapshots[0], False), (snapshots[1], False)],
        ):
            assert _ban(api, staff["adm"]).status_code == 200
            assert _ban(api, staff["mod"]).status_code == 200
        assert _membership(community, mem).banned_by == staff["adm"]
        assert ModAction.objects.filter(action=ModAction.Action.USER_BAN).count() == 1
        assert Notification.objects.filter(recipient=mem, verb="mod_action").count() == 1

    def test_unban_does_not_lift_a_ban_reissued_meanwhile(self, api, community, staff):
        _ban(api, staff["mod"])
        stale = _membership(community, staff["mem"])
        _unban(api, staff["adm"])
        _ban(api, staff["adm"])
        with patch.object(CommunityBanView, "_find_membership", return_value=stale):
            assert _unban(api, staff["mod"]).status_code == 204
        m = _membership(community, staff["mem"])
        assert (m.is_banned, m.banned_by) == (True, staff["adm"])
        assert ModAction.objects.filter(action=ModAction.Action.USER_UNBAN).count() == 1

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.communities.models import Community, Membership
from apps.communities.services import roles_below
from apps.moderation.models import ModAction

User = get_user_model()


def membership_url(slug):
    return reverse("api_v1:communities:community-membership", args=[slug])


def ban_url(slug, username):
    return reverse("api_v1:moderation:community-mod-ban", args=[slug, username])


def _user(name):
    return User.objects.create_user(username=name, email=f"{name}@x.com", password="StrongPass123!")


@pytest.fixture
def creator(db):
    return _user("creator")


@pytest.fixture
def community(creator):
    return Community.objects.create(slug="py", name="Py", creator=creator)


@pytest.fixture
def mod(community):
    user = _user("mod")
    Membership.objects.create(user=user, community=community, role=Membership.Role.MODERATOR)
    return user


@pytest.fixture
def member(community):
    user = _user("member")
    Membership.objects.create(user=user, community=community)
    return user


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _ban_before_delete(member, community, mod):
    """Run the mod's ban UPDATE right before the leave's DELETE reaches the database."""
    fired = False

    def wrapper(execute, sql, params, many, context):
        nonlocal fired
        if not fired and sql.startswith('DELETE FROM "communities_membership"'):
            fired = True
            Membership.objects.filter(user=member, community=community).update(
                is_banned=True, banned_by=mod, banned_at=timezone.now()
            )
        return execute(sql, params, many, context)

    return wrapper


def _delete_membership_then(real, member, community):
    def side_effect(actor, comm):
        result = real(actor, comm)
        Membership.objects.filter(user=member, community=comm).delete()
        return result

    return side_effect


@pytest.mark.django_db
def test_ban_landing_before_leave_is_kept(member, community, mod):
    with connection.execute_wrapper(_ban_before_delete(member, community, mod)):
        resp = _client(member).delete(membership_url(community.slug))
    banned = Membership.objects.get(user=member, community=community)
    assert resp.status_code == 400
    assert banned.is_banned


@pytest.mark.django_db
def test_leave_without_membership_is_idempotent(community):
    resp = _client(_user("stranger")).delete(membership_url(community.slug))
    assert resp.status_code == 204


@pytest.mark.django_db
def test_ban_when_member_left_mid_request(member, community, mod):
    side_effect = _delete_membership_then(roles_below, member, community)
    with patch("apps.moderation.views.roles_below", side_effect=side_effect):
        resp = _client(mod).post(ban_url(community.slug, member.username))
    banned = Membership.objects.get(user=member, community=community)
    assert resp.status_code == 200
    assert banned.is_banned
    assert banned.role == Membership.Role.MEMBER
    assert banned.banned_by == mod
    assert banned.banned_at is not None
    assert ModAction.objects.filter(action=ModAction.Action.USER_BAN).count() == 1

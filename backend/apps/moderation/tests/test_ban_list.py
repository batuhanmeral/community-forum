import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.communities.models import Community, Membership

User = get_user_model()


def bans_url(slug):
    return reverse("api_v1:moderation:community-mod-bans", args=[slug])


def _user(name):
    return User.objects.create_user(username=name, email=f"{name}@x.com", password="x")


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def owner(db):
    return _user("owner")


@pytest.fixture
def community(owner):
    return Community.objects.create(slug="py", name="Py", creator=owner)


def _ban(community, name, issuer):
    user = _user(name)
    Membership.objects.create(
        user=user, community=community, is_banned=True, banned_by=issuer, banned_at=timezone.now()
    )
    return user


@pytest.mark.django_db
class TestBanList:
    def test_anonymous_and_members_are_refused(self, api, community):
        assert api.get(bans_url("py")).status_code == 401
        member = _user("member")
        Membership.objects.create(user=member, community=community)
        api.force_authenticate(member)
        assert api.get(bans_url("py")).status_code == 403

    def test_lists_only_this_communitys_bans_newest_first(self, api, owner, community):
        other = Community.objects.create(slug="js", name="Js", creator=owner)
        _ban(community, "first", owner)
        _ban(community, "second", owner)
        _ban(other, "elsewhere", owner)
        Membership.objects.create(user=_user("active"), community=community)
        api.force_authenticate(owner)
        rows = api.get(bans_url("py")).data["results"]
        assert [r["username"] for r in rows] == ["second", "first"]

    def test_row_shows_issuer_but_no_personal_data(self, api, owner, community):
        _ban(community, "spammer", owner)
        api.force_authenticate(owner)
        row = api.get(bans_url("py")).data["results"][0]
        assert row["banned_by_username"] == "owner"
        assert set(row) == {
            "id",
            "username",
            "avatar",
            "banned_by_username",
            "banned_at",
            "joined_at",
        }

    def test_query_count_does_not_grow_with_bans(self, api, owner, community):
        api.force_authenticate(owner)
        _ban(community, "b1", owner)
        with CaptureQueriesContext(connection) as one:
            api.get(bans_url("py"))
        for i in range(2, 6):
            _ban(community, f"b{i}", owner)
        with CaptureQueriesContext(connection) as five:
            api.get(bans_url("py"))
        assert len(five) == len(one)

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.communities.models import Community, CommunityRule, Membership

User = get_user_model()


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


def list_url(slug):
    return reverse("api_v1:communities:community-rules", args=[slug])


def detail_url(slug, pk):
    return reverse("api_v1:communities:community-rule-detail", args=[slug, pk])


@pytest.mark.django_db
class TestRules:
    def test_anyone_can_list(self, api, community):
        CommunityRule.objects.create(community=community, order=0, short="Be nice")
        resp = api.get(list_url("py"))
        assert resp.status_code == 200
        assert resp.data["count"] == 1

    def test_non_mod_cannot_create(self, api, bob, community):
        api.force_authenticate(bob)
        resp = api.post(list_url("py"), {"short": "No spam"}, format="json")
        assert resp.status_code == 403

    def test_creator_admin_can_create(self, api, alice, community):
        api.force_authenticate(alice)
        resp = api.post(
            list_url("py"), {"short": "No spam", "description": "Don't."}, format="json"
        )
        assert resp.status_code == 201
        assert CommunityRule.objects.count() == 1

    def test_mod_can_update_and_delete(self, api, bob, community):
        Membership.objects.create(user=bob, community=community, role=Membership.Role.MODERATOR)
        rule = CommunityRule.objects.create(community=community, short="x")
        api.force_authenticate(bob)
        resp = api.patch(detail_url("py", rule.id), {"short": "y"}, format="json")
        assert resp.status_code == 200
        assert api.delete(detail_url("py", rule.id)).status_code == 204

    def test_ordered_by_order(self, api, community):
        CommunityRule.objects.create(community=community, order=2, short="b")
        CommunityRule.objects.create(community=community, order=1, short="a")
        resp = api.get(list_url("py"))
        shorts = [r["short"] for r in resp.data["results"]]
        assert shorts == ["a", "b"]

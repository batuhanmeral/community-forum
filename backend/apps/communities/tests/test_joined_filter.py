import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.communities.models import Community, Membership

User = get_user_model()
LIST = reverse("api_v1:communities:community-list")


@pytest.mark.django_db
def test_joined_filter_lists_only_active_memberships():
    owner = User.objects.create_user(username="owner", email="o@x.com", password="x")
    me = User.objects.create_user(username="me", email="me@x.com", password="x")
    joined = Community.objects.create(slug="joined", name="J", creator=owner)
    banned = Community.objects.create(slug="banned", name="B", creator=owner)
    Community.objects.create(slug="other", name="O", creator=owner)
    Membership.objects.create(user=me, community=joined)
    Membership.objects.create(user=me, community=banned, is_banned=True)

    client = APIClient()
    client.force_authenticate(me)
    slugs = [c["slug"] for c in client.get(LIST, {"joined": "true"}).data["results"]]
    assert slugs == ["joined"]
    assert APIClient().get(LIST, {"joined": "true"}).data["results"] == []


@pytest.mark.django_db
def test_listing_looks_up_each_membership_once(django_assert_max_num_queries):
    owner = User.objects.create_user(username="owner", email="o@x.com", password="x")
    me = User.objects.create_user(username="me", email="me@x.com", password="x")
    for i in range(10):
        community = Community.objects.create(slug=f"c{i}", name=f"C{i}", creator=owner)
        Membership.objects.create(user=me, community=community)

    client = APIClient()
    client.force_authenticate(me)
    # The viewer's memberships are prefetched, so the count no longer grows per community.
    with django_assert_max_num_queries(5):
        resp = client.get(LIST, {"joined": "true"})
    assert len(resp.data["results"]) == 10

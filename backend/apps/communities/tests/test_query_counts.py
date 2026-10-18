import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient

from apps.communities.models import Community, Membership

User = get_user_model()

LIST = reverse("api_v1:communities:community-list")
SEARCH = reverse("api_v1:search:search")
TRENDING = reverse("api_v1:search:trending-communities")


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()


@pytest.fixture
def owner(db):
    return User.objects.create_user(username="owner", email="owner@x.com", password="x")


@pytest.fixture
def viewer(db):
    return User.objects.create_user(username="viewer", email="viewer@x.com", password="x")


@pytest.fixture
def api(viewer):
    client = APIClient()
    client.force_authenticate(viewer)
    return client


@pytest.fixture
def viewer_in_ten_communities(owner, viewer):
    for i in range(10):
        community = Community.objects.create(slug=f"c{i}", name=f"Python {i}", creator=owner)
        Membership.objects.create(user=viewer, community=community)


@pytest.fixture
def community_with_keywords(owner):
    return Community.objects.create(
        slug="kw", name="Keywords", creator=owner, banned_keywords="spam\nscam"
    )


@pytest.mark.parametrize(
    "url", [LIST, LIST + "?joined=true", SEARCH + "?q=python&type=community", TRENDING]
)
def test_ten_communities_within_five_queries(
    api, viewer_in_ten_communities, url, django_assert_max_num_queries
):
    with django_assert_max_num_queries(5):
        resp = api.get(url)
    assert len(resp.data["results"]) == 10


def test_anonymous_list_reads_no_membership_rows(viewer_in_ten_communities):
    with CaptureQueriesContext(connection) as ctx:
        resp = APIClient().get(LIST)
    assert len(resp.data["results"]) == 10
    # member_count joins the table; a standalone SELECT would be a viewer prefetch.
    assert not [q for q in ctx.captured_queries if 'FROM "communities_membership"' in q["sql"]]


@pytest.mark.parametrize(
    "state, expected",
    [
        ("member", {"is_member": True, "my_role": "member", "is_banned": False, "keywords": False}),
        ("banned_mod", {"is_member": False, "my_role": None, "is_banned": True, "keywords": False}),
        (
            "moderator",
            {"is_member": True, "my_role": "moderator", "is_banned": False, "keywords": True},
        ),
        ("none", {"is_member": False, "my_role": None, "is_banned": False, "keywords": False}),
    ],
)
def test_prefetched_membership_matches_viewer_state(
    api, viewer, community_with_keywords, state, expected
):
    community = community_with_keywords
    # The creator's admin row (made on create) must never be read as the viewer's.
    if state == "member":
        Membership.objects.create(user=viewer, community=community)
    elif state == "banned_mod":
        Membership.objects.create(
            user=viewer, community=community, role="moderator", is_banned=True
        )
    elif state == "moderator":
        Membership.objects.create(user=viewer, community=community, role="moderator")

    detail = api.get(reverse("api_v1:communities:community-detail", args=[community.slug])).data
    row = next(c for c in api.get(LIST).data["results"] if c["slug"] == community.slug)

    for payload in (row, detail):
        assert payload["is_member"] is expected["is_member"]
        assert payload["my_role"] == expected["my_role"]
        assert payload["is_banned"] is expected["is_banned"]
        assert ("banned_keywords" in payload) is expected["keywords"]
        if not expected["is_member"]:
            assert payload["my_notify_level"] is None

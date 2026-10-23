import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.communities.models import Community

User = get_user_model()
LIST = reverse("api_v1:communities:community-list")


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="alice", email="a@x.com", password="x")


@pytest.fixture
def communities(alice):
    Community.objects.create(slug="pysafe", name="Python", creator=alice)
    Community.objects.create(slug="pyadult", name="Python Adult", creator=alice, is_nsfw=True)


def _slugs(resp):
    return {c["slug"] for c in resp.data["results"]}


@pytest.mark.django_db
class TestCommunityListNsfw:
    def test_community_list_search_hides_nsfw(self, communities):
        resp = APIClient().get(LIST, {"search": "python"})
        assert _slugs(resp) == {"pysafe"}

    def test_community_list_search_shows_nsfw_with_opt_in(self, communities, alice):
        client = APIClient()
        client.force_authenticate(alice)
        resp = client.get(LIST, {"search": "python", "nsfw": "show"})
        assert _slugs(resp) == {"pysafe", "pyadult"}
        alice.show_nsfw = True
        alice.save(update_fields=["show_nsfw"])
        assert _slugs(client.get(LIST, {"search": "python"})) == {"pysafe", "pyadult"}

    def test_community_list_browse_unchanged(self, communities):
        assert _slugs(APIClient().get(LIST)) == {"pysafe", "pyadult"}

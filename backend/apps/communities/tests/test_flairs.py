import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.communities.models import Community, Flair, Membership
from apps.posts.models import Post

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
    return reverse("api_v1:communities:community-flairs", args=[slug])


def detail_url(slug, pk):
    return reverse("api_v1:communities:community-flair-detail", args=[slug, pk])


@pytest.mark.django_db
class TestFlairs:
    def test_anyone_can_list(self, api, community):
        Flair.objects.create(community=community, name="Help", color="#ff0000")
        resp = api.get(list_url("py"))
        assert resp.status_code == 200
        assert [f["name"] for f in resp.data] == ["Help"]

    def test_non_mod_cannot_create(self, api, bob, community):
        api.force_authenticate(bob)
        resp = api.post(list_url("py"), {"name": "News"}, format="json")
        assert resp.status_code == 403

    def test_creator_admin_can_create(self, api, alice, community):
        api.force_authenticate(alice)
        resp = api.post(list_url("py"), {"name": "News", "color": "#00ff00"}, format="json")
        assert resp.status_code == 201
        assert Flair.objects.filter(community=community, name="News").exists()

    def test_mod_can_delete(self, api, bob, community):
        Membership.objects.create(user=bob, community=community, role=Membership.Role.MODERATOR)
        flair = Flair.objects.create(community=community, name="Old")
        api.force_authenticate(bob)
        resp = api.delete(detail_url("py", flair.pk))
        assert resp.status_code == 204
        assert not Flair.objects.filter(pk=flair.pk).exists()

    def test_non_mod_cannot_delete(self, api, bob, community):
        flair = Flair.objects.create(community=community, name="Keep")
        api.force_authenticate(bob)
        resp = api.delete(detail_url("py", flair.pk))
        assert resp.status_code == 403

    def test_post_serializes_flair_detail(self, api, alice, community):
        flair = Flair.objects.create(community=community, name="Help", color="#ff0000")
        post = Post.objects.create(
            author=alice, community=community, kind="text", title="t", flair=flair
        )
        resp = api.get(reverse("api_v1:posts:post-detail", args=[post.pk]))
        assert resp.status_code == 200
        assert resp.data["flair_detail"] == {"id": flair.pk, "name": "Help", "color": "#ff0000"}

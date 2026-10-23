import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

User = get_user_model()

ME = reverse("api_v1:users:users-me")
PASSWORD = reverse("api_v1:users:users-change-password")
LOGIN = reverse("api_v1:auth:auth-login")

OLD_PW = "OldStrongPass123!"
NEW_PW = "NewStrongPass456!"


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="alice", email="a@x.com", password=OLD_PW)


@pytest.mark.django_db
class TestChangePassword:
    def test_requires_auth(self, api):
        assert api.post(PASSWORD, {}).status_code == 401

    def test_wrong_current_password_rejected(self, api, alice):
        api.force_authenticate(alice)
        resp = api.post(
            PASSWORD,
            {"current_password": "wrong", "new_password": NEW_PW},
            format="json",
        )
        assert resp.status_code == 400
        assert "current_password" in resp.data

    def test_weak_new_password_rejected(self, api, alice):
        api.force_authenticate(alice)
        resp = api.post(
            PASSWORD,
            {"current_password": OLD_PW, "new_password": "123"},
            format="json",
        )
        assert resp.status_code == 400
        assert "new_password" in resp.data

    def test_success_allows_login_with_new_password(self, api, alice):
        api.force_authenticate(alice)
        resp = api.post(
            PASSWORD,
            {"current_password": OLD_PW, "new_password": NEW_PW},
            format="json",
        )
        assert resp.status_code == 200
        fresh = APIClient()
        assert (
            fresh.post(LOGIN, {"username": "alice", "password": OLD_PW}, format="json").status_code
            == 401
        )
        assert (
            fresh.post(LOGIN, {"username": "alice", "password": NEW_PW}, format="json").status_code
            == 200
        )


@pytest.mark.django_db
class TestNsfwPreference:
    def test_patch_show_nsfw(self, api, alice):
        api.force_authenticate(alice)
        resp = api.patch(ME, {"show_nsfw": True}, format="json")
        assert resp.status_code == 200
        assert resp.data["show_nsfw"] is True
        alice.refresh_from_db()
        assert alice.show_nsfw is True

    def test_public_profile_hides_email_and_pref(self, api, alice):
        resp = api.get(reverse("api_v1:users:users-profile", args=["alice"]))
        assert "email" not in resp.data
        assert "show_nsfw" not in resp.data

    def test_feed_respects_server_pref(self, api, alice):
        from apps.communities.models import Community, Membership
        from apps.posts.models import Post

        community = Community.objects.create(slug="py", name="Py", creator=alice)
        Membership.objects.get_or_create(user=alice, community=community)
        nsfw = Post.objects.create(
            author=alice, community=community, kind="text", title="n", is_nsfw=True
        )
        api.force_authenticate(alice)
        feed = reverse("api_v1:feed:feed")
        ids = [p["id"] for p in api.get(feed).data["results"]]
        assert nsfw.id not in ids
        alice.show_nsfw = True
        alice.save(update_fields=["show_nsfw"])
        ids = [p["id"] for p in api.get(feed).data["results"]]
        assert nsfw.id in ids
        # explicit param overrides the stored preference
        ids = [p["id"] for p in api.get(feed, {"nsfw": "hide"}).data["results"]]
        assert nsfw.id not in ids

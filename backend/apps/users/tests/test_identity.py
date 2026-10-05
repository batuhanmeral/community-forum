import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.db import IntegrityError
from django.urls import reverse
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

User = get_user_model()
ME = reverse("api_v1:users:users-me")
REGISTER = reverse("api_v1:auth:auth-register")


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="alice", email="a@x.com", password="StrongPass123!")


@pytest.fixture
def bob(db):
    user = User.objects.create_user(username="bob", email="b@x.com", password="StrongPass123!")
    user.email_verified = True
    user.save(update_fields=["email_verified"])
    return user


@pytest.mark.django_db
class TestMeUpdate:
    def test_username_is_read_only(self, api, alice, bob):
        api.force_authenticate(bob)
        assert api.patch(ME, {"username": "Alice"}, format="json").status_code == 200
        bob.refresh_from_db()
        assert bob.username == "bob"
        assert (
            APIClient().get(reverse("api_v1:users:users-profile", args=["alice"])).status_code
            == 200
        )

    def test_email_taken_case_insensitively_rejected(self, api, alice, bob):
        api.force_authenticate(bob)
        resp = api.patch(ME, {"email": "A@X.com"}, format="json")
        assert resp.status_code == 400
        assert "email" in resp.data

    def test_email_change_requires_reverification(self, api, bob):
        api.force_authenticate(bob)
        resp = api.patch(
            ME,
            {"email": "new@x.com", "current_password": "StrongPass123!"},
            format="json",
        )
        assert resp.status_code == 200
        assert "current_password" not in resp.data
        bob.refresh_from_db()
        assert bob.email == "new@x.com"
        assert bob.email_verified is False
        assert mail.outbox[-1].to == ["new@x.com"]

    def test_email_change_without_password_rejected(self, api, bob):
        api.force_authenticate(bob)
        resp = api.patch(ME, {"email": "new@x.com"}, format="json")
        assert resp.status_code == 400
        assert "current_password" in resp.data
        bob.refresh_from_db()
        assert bob.email == "b@x.com"

    def test_email_change_with_wrong_password_rejected(self, api, bob):
        api.force_authenticate(bob)
        resp = api.patch(ME, {"email": "new@x.com", "current_password": "nope"}, format="json")
        assert resp.status_code == 400
        assert "current_password" in resp.data
        bob.refresh_from_db()
        assert bob.email == "b@x.com"

    def test_case_only_email_change_needs_no_password(self, api, bob):
        api.force_authenticate(bob)
        assert api.patch(ME, {"email": "B@X.com"}, format="json").status_code == 200

    def test_email_change_patch_is_throttled_but_other_patches_are_not(self, api, bob, monkeypatch):
        from rest_framework.throttling import ScopedRateThrottle

        monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"auth": "1/min"})
        api.force_authenticate(bob)
        body = {"email": "new@x.com", "current_password": "StrongPass123!"}
        assert api.patch(ME, body, format="json").status_code == 200
        assert api.patch(ME, body, format="json").status_code == 429
        assert api.patch(ME, {"bio": "hi"}, format="json").status_code == 200
        assert api.get(ME).status_code == 200

    def test_blank_email_rejected(self, api, bob):
        api.force_authenticate(bob)
        assert api.patch(ME, {"email": ""}, format="json").status_code == 400

    def test_same_email_keeps_verification(self, api, bob):
        api.force_authenticate(bob)
        api.patch(ME, {"email": "B@x.com", "bio": "hi"}, format="json")
        bob.refresh_from_db()
        assert bob.email_verified is True


@pytest.mark.django_db
class TestRegisterUsername:
    @pytest.mark.parametrize("name", ["ab", "john.doe", "x" * 31, "çağrı", "a b"])
    def test_rejects_outside_charset(self, api, name):
        resp = api.post(
            REGISTER,
            {"username": name, "email": "n@x.com", "password": "StrongPass123!"},
            format="json",
        )
        assert resp.status_code == 400
        assert "username" in resp.data

    def test_rejects_trailing_newline(self):
        from apps.users.serializers import RegisterSerializer

        with pytest.raises(ValidationError):
            RegisterSerializer().validate_username("abc\n")

    def test_accepts_letters_digits_underscore(self, api):
        resp = api.post(
            REGISTER,
            {"username": "dev_42", "email": "d@x.com", "password": "StrongPass123!"},
            format="json",
        )
        assert resp.status_code == 201


@pytest.mark.django_db
class TestDatabaseConstraints:
    def test_username_unique_ignoring_case(self, alice):
        with pytest.raises(IntegrityError):
            User.objects.create_user(username="ALICE", email="other@x.com", password="x")

    def test_email_unique_ignoring_case(self, alice):
        with pytest.raises(IntegrityError):
            User.objects.create_user(username="other", email="A@x.com", password="x")

    def test_multiple_blank_emails_allowed(self, db):
        User.objects.create_user(username="nomail1", email="", password="x")
        User.objects.create_user(username="nomail2", email="", password="x")

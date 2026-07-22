import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

User = get_user_model()

PREVIEW = reverse("api_v1:common:markdown-preview")


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="alice", email="a@x.com", password="x")


@pytest.mark.django_db
class TestMarkdownPreview:
    def test_requires_auth(self, api):
        assert api.post(PREVIEW, {"body": "x"}, format="json").status_code == 401

    def test_renders_markdown(self, api, alice):
        api.force_authenticate(alice)
        resp = api.post(PREVIEW, {"body": "**bold** text"}, format="json")
        assert resp.status_code == 200
        assert "<strong>bold</strong>" in resp.data["html"]

    def test_sanitizes_script(self, api, alice):
        api.force_authenticate(alice)
        resp = api.post(PREVIEW, {"body": "<script>alert(1)</script>hi"}, format="json")
        assert "<script" not in resp.data["html"]
        assert "hi" in resp.data["html"]

    def test_empty_body_ok(self, api, alice):
        api.force_authenticate(alice)
        resp = api.post(PREVIEW, {"body": ""}, format="json")
        assert resp.status_code == 200
        assert resp.data["html"] == ""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.communities.models import Community, Membership

User = get_user_model()


@pytest.fixture
def qa(db):
    owner = User.objects.create_user(username="owner", email="owner@example.com")
    answerer = User.objects.create_user(username="answerer", email="answer@example.com")
    other = User.objects.create_user(username="other", email="other@example.com")
    community = Community.objects.create(slug="questions", name="Questions", creator=owner)
    Membership.objects.get_or_create(user=owner, community=community, defaults={"role": "admin"})
    api = APIClient()
    api.force_authenticate(owner)
    return api, owner, answerer, other, community

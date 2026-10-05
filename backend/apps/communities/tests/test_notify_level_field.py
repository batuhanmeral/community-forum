import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.communities.models import Community, Membership

User = get_user_model()


@pytest.mark.django_db
def test_my_notify_level_reflects_membership():
    owner = User.objects.create_user(username="owner", email="o@x.com", password="x")
    member = User.objects.create_user(username="member", email="m@x.com", password="x")
    Community.objects.create(slug="py", name="Py", creator=owner)
    Membership.objects.create(
        user=member,
        community=Community.objects.get(slug="py"),
        notify_level=Membership.NotifyLevel.POSTS_ONLY,
    )
    url = reverse("api_v1:communities:community-detail", args=["py"])

    client = APIClient()
    client.force_authenticate(member)
    assert client.get(url).data["my_notify_level"] == "posts_only"
    assert APIClient().get(url).data["my_notify_level"] is None

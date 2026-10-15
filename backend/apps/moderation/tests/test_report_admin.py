import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from apps.communities.models import Community
from apps.moderation.models import Report
from apps.posts.models import Post

User = get_user_model()
CHANGELIST = reverse("admin:moderation_report_changelist")


def _report(reporter, target):
    return Report.objects.create(
        reporter=reporter,
        content_type=ContentType.objects.get_for_model(target.__class__),
        object_id=target.pk,
        reason="r",
    )


@pytest.fixture
def reports(db):
    owner = User.objects.create_user(username="owner", email="o@x.com", password="x")
    community = Community.objects.create(slug="py", name="Py", creator=owner)
    post = Post.objects.create(author=owner, community=community, title="t")
    return {"post": _report(owner, post), "user": _report(owner, owner), "target": post}


@pytest.mark.django_db
class TestReportAdmin:
    def test_filters_user_reports(self, admin_client, reports):
        resp = admin_client.get(CHANGELIST, {"target_type": "user"})
        assert resp.status_code == 200
        assert list(resp.context["cl"].result_list) == [reports["user"]]

    def test_links_to_the_target_admin_page(self, admin_client, reports):
        resp = admin_client.get(CHANGELIST, {"target_type": "post"})
        target_url = reverse("admin:posts_post_change", args=[reports["target"].pk])
        assert target_url in resp.content.decode()

    def test_unknown_target_type_shows_a_dash(self, admin_client, reports):
        owner = reports["target"].author
        Report.objects.create(
            reporter=owner,
            content_type=ContentType.objects.get_for_model(ContentType),
            object_id=1,
            reason="r",
        )
        resp = admin_client.get(CHANGELIST)
        assert resp.status_code == 200
        assert '<td class="field-target_link">-</td>' in resp.content.decode()

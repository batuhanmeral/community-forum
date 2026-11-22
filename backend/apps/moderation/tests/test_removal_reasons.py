import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.comments.models import Comment
from apps.communities.models import Community, Membership
from apps.moderation.models import ModAction, RemovalReason
from apps.notifications.models import Notification
from apps.posts.models import Post
from apps.social.models import Block

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def world():
    users = {
        name: User.objects.create_user(username=name, email=f"{name}@example.test", password="x")
        for name in ("admin", "author", "bystander")
    }
    community = Community.objects.create(slug="rr", name="RR", creator=users["admin"])
    for name in ("author", "bystander"):
        Membership.objects.create(user=users[name], community=community)
    post = Post.objects.create(author=users["author"], community=community, title="Spam post")
    comment = Comment.objects.create(author=users["author"], post=post, body="spam")
    api = APIClient()
    api.force_authenticate(users["admin"])
    return api, users, community, post, comment


def templates(community):
    return f"/api/v1/communities/{community.slug}/mod/removal-reasons/"


def make_reason(community, **kwargs):
    data = {"title": "Spam", "body": "No **spam** please <script>alert(1)</script>"}
    data.update(kwargs)
    return RemovalReason.objects.create(community=community, **data)


def test_only_moderators_manage_templates(world):
    api, users, community, *_ = world
    assert api.post(templates(community), {"title": "Spam", "body": "x"}).status_code == 201
    api.force_authenticate(users["bystander"])
    assert api.get(templates(community)).status_code == 403
    assert api.post(templates(community), {"title": "Spam", "body": "x"}).status_code == 403
    api.force_authenticate(None)
    assert api.get(templates(community)).status_code in (401, 403)


def test_template_limits(world):
    api, _, community, *_ = world
    assert api.post(templates(community), {"title": "x" * 61, "body": "b"}).status_code == 400
    assert api.post(templates(community), {"title": "t", "body": "b" * 1001}).status_code == 400
    for i in range(25):
        assert api.post(templates(community), {"title": f"T{i}", "body": "b"}).status_code == 201
    assert api.post(templates(community), {"title": "Extra", "body": "b"}).status_code == 400


def test_template_update_and_delete(world):
    api, _, community, *_ = world
    reason = make_reason(community)
    url = templates(community) + f"{reason.pk}/"
    assert api.patch(url, {"title": "Renamed"}, format="json").status_code == 200
    assert api.delete(url).status_code == 204
    assert not RemovalReason.objects.filter(pk=reason.pk).exists()


def test_removing_post_records_reason_and_notifies_author(world):
    api, users, community, post, _ = world
    reason = make_reason(community)
    response = api.delete(
        f"/api/v1/posts/{post.pk}/", {"removal_reason": reason.pk, "removal_note": "Third time"}
    )
    assert response.status_code == 204
    action = ModAction.objects.get(community=community, action="post_remove")
    assert (action.reason_title, action.reason_note) == ("Spam", "Third time")
    note = Notification.objects.get(recipient=users["author"], verb="removal")
    assert note.reason_title == "Spam"
    assert "<strong>spam</strong>" in note.reason_body_html
    assert "<script" not in note.reason_body_html
    assert "Third time" in note.reason_body_html


def test_removing_comment_records_reason(world):
    api, users, community, _, comment = world
    reason = make_reason(community)
    assert (
        api.delete(f"/api/v1/comments/{comment.pk}/", {"removal_reason": reason.pk}).status_code
        == 204
    )
    assert ModAction.objects.get(action="comment_remove").reason_title == "Spam"
    assert Notification.objects.filter(recipient=users["author"], verb="removal").exists()


def test_log_exposes_title_only_and_old_entries_survive_edits(world):
    api, _, community, post, _ = world
    reason = make_reason(community)
    api.delete(f"/api/v1/posts/{post.pk}/", {"removal_reason": reason.pk, "removal_note": "secret"})
    RemovalReason.objects.filter(pk=reason.pk).update(title="Changed", body="Changed")
    log = api.get(f"/api/v1/communities/{community.slug}/mod/log/").data["results"]
    entry = next(e for e in log if e["action"] == "post_remove")
    assert entry["reason_title"] == "Spam"
    assert "reason_body" not in entry and "reason_note" not in entry
    reason.delete()
    assert ModAction.objects.get(action="post_remove").reason_title == "Spam"


def test_reason_from_another_community_is_rejected_without_removing(world):
    api, users, community, post, _ = world
    other = Community.objects.create(slug="other", name="Other", creator=users["admin"])
    foreign = make_reason(other)
    response = api.delete(f"/api/v1/posts/{post.pk}/", {"removal_reason": foreign.pk})
    assert response.status_code == 400
    post.refresh_from_db()
    assert post.deleted_at is None


def test_note_length_is_capped(world):
    api, _, community, post, _ = world
    reason = make_reason(community)
    response = api.delete(
        f"/api/v1/posts/{post.pk}/", {"removal_reason": reason.pk, "removal_note": "n" * 501}
    )
    assert response.status_code == 400


def test_require_removal_reason_blocks_bare_mod_removal(world):
    api, users, community, post, comment = world
    community.require_removal_reason = True
    community.save()
    reason = make_reason(community)  # the requirement only applies once templates exist
    assert api.delete(f"/api/v1/posts/{post.pk}/").status_code == 400
    assert api.delete(f"/api/v1/comments/{comment.pk}/").status_code == 400
    post.refresh_from_db()
    assert post.deleted_at is None
    assert api.delete(f"/api/v1/posts/{post.pk}/", {"removal_reason": reason.pk}).status_code == 204
    # Authors deleting their own content are not asked for a reason.
    api.force_authenticate(users["author"])
    assert api.delete(f"/api/v1/comments/{comment.pk}/").status_code == 204


def test_author_self_delete_ignores_reason_fields(world):
    api, users, community, post, _ = world
    reason = make_reason(community)
    api.force_authenticate(users["author"])
    assert api.delete(f"/api/v1/posts/{post.pk}/", {"removal_reason": reason.pk}).status_code == 204
    assert not ModAction.objects.filter(action="post_remove").exists()
    assert not Notification.objects.filter(verb="removal").exists()


def test_blocked_moderator_removal_sends_no_notification(world):
    api, users, community, post, _ = world
    Block.objects.create(blocker=users["author"], blocked=users["admin"])
    reason = make_reason(community)
    assert api.delete(f"/api/v1/posts/{post.pk}/", {"removal_reason": reason.pk}).status_code == 204
    assert not Notification.objects.filter(recipient=users["author"], verb="removal").exists()


def test_notification_api_exposes_reason(world):
    api, users, community, post, _ = world
    reason = make_reason(community)
    api.delete(f"/api/v1/posts/{post.pk}/", {"removal_reason": reason.pk})
    api.force_authenticate(users["author"])
    results = api.get("/api/v1/notifications/").data["results"]
    item = next(n for n in results if n["verb"] == "removal")
    assert item["reason_title"] == "Spam"
    assert "<strong>spam</strong>" in item["reason_body_html"]
    assert item["link"] == f"/posts/{post.pk}"


def test_requirement_is_only_enforced_when_templates_exist(world):
    api, users, community, post, _ = world
    community.require_removal_reason = True
    community.save()
    # No templates yet: a moderator must still be able to remove content.
    assert api.delete(f"/api/v1/posts/{post.pk}/").status_code == 204


def test_requirement_cannot_be_enabled_without_templates(world):
    api, users, community, *_ = world
    url = f"/api/v1/communities/{community.slug}/"
    assert api.patch(url, {"require_removal_reason": True}, format="json").status_code == 400
    community.refresh_from_db()
    assert community.require_removal_reason is False
    make_reason(community)
    assert api.patch(url, {"require_removal_reason": True}, format="json").status_code == 200
    # Switching it off never needs templates.
    RemovalReason.objects.all().delete()
    assert api.patch(url, {"require_removal_reason": False}, format="json").status_code == 200

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.communities.models import Community, Membership
from apps.moderation.models import ModAction

pytestmark = pytest.mark.django_db


@pytest.fixture
def setup():
    users = get_user_model()
    admin = users.objects.create_user(username="owner", email="owner@example.test")
    member = users.objects.create_user(username="member", email="member@example.test")
    community = Community.objects.create(slug="flair", name="Flair", creator=admin)
    Membership.objects.create(user=member, community=community)
    api = APIClient()
    api.force_authenticate(admin)
    return api, admin, member, community


def url(community):
    return f"/api/v1/communities/{community.slug}/user-flairs/"


def test_mod_creates_and_logs_flair(setup):
    api, admin, member, community = setup
    response = api.post(url(community), {"text": "Helper", "color": "#123456"})
    assert response.status_code == 201
    assert response.data["text"] == "Helper"
    assert ModAction.objects.filter(community=community, action="user_flair_create").exists()


def test_nonmod_cannot_create(setup):
    api, admin, member, community = setup
    api.force_authenticate(member)
    assert api.post(url(community), {"text": "Impersonation"}).status_code == 403


def test_self_selection_requires_opt_in_and_clears(setup):
    api, admin, member, community = setup
    created = api.post(url(community), {"text": "Helper"})
    assert created.status_code == 201
    endpoint = f"/api/v1/communities/{community.slug}/user-flair/"
    api.force_authenticate(member)
    assert api.patch(endpoint, {"user_flair": created.data["id"]}).status_code == 403
    community.allow_self_user_flair = True
    community.save()
    response = api.patch(endpoint, {"user_flair": created.data["id"]})
    assert response.status_code == 200
    assert (
        Membership.objects.get(user=member, community=community).user_flair_id == created.data["id"]
    )
    assert api.patch(endpoint, {"user_flair": None}, format="json").status_code == 200
    assert Membership.objects.get(user=member, community=community).user_flair_id is None


def test_input_limits_and_color(setup):
    api, admin, member, community = setup
    for payload in ({"text": "x" * 41}, {"text": "ok", "color": "red"}):
        assert api.post(url(community), payload).status_code == 400
    for i in range(30):
        assert api.post(url(community), {"text": f"Flair {i}"}).status_code == 201
    assert api.post(url(community), {"text": "Extra"}).status_code == 400


def test_author_flair_is_batched_and_hidden_on_deleted_content(
    setup, django_assert_max_num_queries
):
    from apps.comments.models import Comment
    from apps.communities.models import UserFlair
    from apps.posts.models import Post

    api, admin, member, community = setup
    flair = UserFlair.objects.create(community=community, text="Helper")
    Membership.objects.filter(user=member, community=community).update(user_flair=flair)
    posts = [
        Post.objects.create(author=member, community=community, title=f"Post {i}")
        for i in range(12)
    ]
    comment = Comment.objects.create(author=member, post=posts[0], body="Hello")
    with django_assert_max_num_queries(12):
        response = api.get(f"/api/v1/communities/{community.slug}/posts/")
        assert len(response.data["results"]) == 12
        assert all(p["author_flair"]["text"] == "Helper" for p in response.data["results"])
    response = api.get(f"/api/v1/posts/{posts[0].pk}/comments/")
    assert response.data["results"][0]["author_flair"]["text"] == "Helper"
    api.force_authenticate(member)
    assert api.delete(f"/api/v1/comments/{comment.pk}/").status_code == 204
    response = api.get(f"/api/v1/posts/{posts[0].pk}/comments/")
    assert response.data["results"][0]["author_flair"] is None


def test_cross_community_assignment_rejected_and_delete_clears_members(setup):
    from apps.communities.models import UserFlair

    api, admin, member, community = setup
    other = Community.objects.create(slug="other", name="Other", creator=admin)
    foreign = UserFlair.objects.create(community=other, text="Foreign")
    endpoint = f"/api/v1/communities/{community.slug}/user-flair/"
    assert api.patch(endpoint, {"user": member.pk, "user_flair": foreign.pk}).status_code == 400
    flair = UserFlair.objects.create(community=community, text="Local")
    assert api.patch(endpoint, {"user": member.pk, "user_flair": flair.pk}).status_code == 200
    assert api.delete(url(community) + f"{flair.pk}/").status_code == 204
    assert Membership.objects.get(user=member, community=community).user_flair_id is None


def test_ban_and_leave_clear_flair(setup):
    from django.urls import reverse

    from apps.communities.models import UserFlair

    api, admin, member, community = setup
    flair = UserFlair.objects.create(community=community, text="Local")
    Membership.objects.filter(user=member, community=community).update(user_flair=flair)
    endpoint = reverse(
        "api_v1:moderation:community-mod-ban", args=[community.slug, member.username]
    )
    assert api.post(endpoint).status_code in (200, 201)
    membership = Membership.objects.get(user=member, community=community)
    assert membership.is_banned and membership.user_flair_id is None
    assert api.delete(endpoint).status_code == 204
    Membership.objects.filter(pk=membership.pk).update(user_flair=flair)
    api.force_authenticate(member)
    assert api.delete(f"/api/v1/communities/{community.slug}/membership/").status_code == 204
    assert not Membership.objects.filter(pk=membership.pk).exists()


def test_self_selection_is_not_written_to_the_mod_log(setup):
    api, admin, member, community = setup
    from apps.communities.models import UserFlair

    flair = UserFlair.objects.create(community=community, text="Helper")
    community.allow_self_user_flair = True
    community.save()
    endpoint = f"/api/v1/communities/{community.slug}/user-flair/"
    api.force_authenticate(member)
    assert api.patch(endpoint, {"user_flair": flair.pk}).status_code == 200
    # A moderator picking their own flair is not a moderation action either.
    api.force_authenticate(admin)
    assert api.patch(endpoint, {"user_flair": flair.pk}).status_code == 200
    assert not ModAction.objects.filter(action="user_flair_assign").exists()
    # Assigning to someone else is.
    assert api.patch(endpoint, {"user": member.pk, "user_flair": flair.pk}).status_code == 200
    assert ModAction.objects.filter(action="user_flair_assign").count() == 1

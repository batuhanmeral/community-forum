import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.communities.models import Community, Membership
from apps.posts.models import Post

User = get_user_model()


@pytest.fixture
def sp(db):
    owner = User.objects.create_user(username="owner", email="o@example.com")
    author = User.objects.create_user(username="author", email="a@example.com")
    mod = User.objects.create_user(username="mod", email="m@example.com")
    other = User.objects.create_user(username="other", email="x@example.com")
    community = Community.objects.create(slug="films", name="Films", creator=owner)
    Membership.objects.create(user=author, community=community, role="member")
    Membership.objects.create(user=other, community=community, role="member")
    Membership.objects.create(user=mod, community=community, role="moderator")
    return community, owner, author, mod, other


def client(user):
    api = APIClient()
    api.force_authenticate(user)
    return api


def create(api, community, **extra):
    return api.post(
        f"/api/v1/communities/{community.slug}/posts/",
        {"title": "Ending", "kind": "text", "body": "he dies", **extra},
        format="json",
    )


@pytest.mark.django_db
class TestSpoilerFlag:
    def test_author_creates_spoiler_post(self, sp):
        community, _, author, _, _ = sp
        response = create(client(author), community, is_spoiler=True)
        assert response.status_code == 201
        assert response.data["is_spoiler"] is True
        assert Post.objects.get(pk=response.data["id"]).is_spoiler is True

    def test_default_is_false_and_listed_in_feeds(self, sp):
        community, _, author, _, _ = sp
        api = client(author)
        create(api, community)
        create(api, community, is_spoiler=True)
        rows = api.get(f"/api/v1/communities/{community.slug}/posts/").data["results"]
        assert sorted(row["is_spoiler"] for row in rows) == [False, True]
        feed = api.get("/api/v1/feed/?scope=all").data["results"]
        assert sorted(row["is_spoiler"] for row in feed) == [False, True]

    def test_author_toggles_without_edit_marker_or_revision(self, sp):
        community, _, author, _, _ = sp
        api = client(author)
        post_id = create(api, community).data["id"]
        before = Post.objects.get(pk=post_id)
        response = api.patch(f"/api/v1/posts/{post_id}/", {"is_spoiler": True}, format="json")
        assert response.status_code == 200
        assert response.data["is_spoiler"] is True
        after = Post.objects.get(pk=post_id)
        assert after.edited_at == before.edited_at
        assert after.revisions.count() == 0
        assert (
            api.patch(f"/api/v1/posts/{post_id}/", {"is_spoiler": False}, format="json").data[
                "is_spoiler"
            ]
            is False
        )

    def test_other_member_cannot_toggle_via_patch(self, sp):
        community, _, author, _, other = sp
        post_id = create(client(author), community).data["id"]
        response = client(other).patch(
            f"/api/v1/posts/{post_id}/", {"is_spoiler": True}, format="json"
        )
        assert response.status_code == 403

    def test_banned_author_cannot_toggle(self, sp):
        community, _, author, _, _ = sp
        api = client(author)
        post_id = create(api, community).data["id"]
        Membership.objects.filter(user=author, community=community).update(is_banned=True)
        response = api.patch(f"/api/v1/posts/{post_id}/", {"is_spoiler": True}, format="json")
        assert response.status_code == 403

    def test_moderator_sets_and_clears_spoiler(self, sp):
        community, _, author, mod, other = sp
        post_id = create(client(author), community).data["id"]
        url = f"/api/v1/posts/{post_id}/spoiler/"
        assert client(other).post(url).status_code == 403
        assert client(mod).post(url).data == {"is_spoiler": True}
        assert client(mod).post(url).data == {"is_spoiler": True}
        assert Post.objects.get(pk=post_id).is_spoiler is True
        assert client(mod).delete(url).data == {"is_spoiler": False}
        assert Post.objects.get(pk=post_id).is_spoiler is False

    def test_moderator_spoiler_toggles_are_in_the_mod_log(self, sp):
        from apps.moderation.models import ModAction

        community, _, author, mod, _ = sp
        post_id = create(client(author), community).data["id"]
        url = f"/api/v1/posts/{post_id}/spoiler/"
        client(mod).post(url)
        client(mod).post(url)  # no change, no second entry
        client(mod).delete(url)
        log = ModAction.objects.filter(community=community, object_id=post_id).order_by("pk")
        assert [(a.action, a.actor_id) for a in log] == [
            ("post_spoiler", mod.pk),
            ("post_unspoiler", mod.pk),
        ]

    def test_moderator_endpoint_hides_held_posts_and_needs_login(self, sp):
        community, _, author, mod, _ = sp
        post_id = create(client(author), community).data["id"]
        assert APIClient().post(f"/api/v1/posts/{post_id}/spoiler/").status_code == 401
        Post.objects.filter(pk=post_id).update(is_approved=False)
        outsider = User.objects.create_user(username="out", email="out@example.com")
        assert client(outsider).post(f"/api/v1/posts/{post_id}/spoiler/").status_code == 404

    def test_removing_spoiler_does_not_requeue_approved_post(self, sp):
        community, _, author, _, _ = sp
        community.requires_approval = True
        community.save()
        post = Post.objects.create(
            author=author, community=community, title="T", body="b", is_spoiler=True
        )
        response = client(author).patch(
            f"/api/v1/posts/{post.pk}/", {"is_spoiler": False}, format="json"
        )
        assert response.status_code == 200
        assert Post.objects.get(pk=post.pk).is_approved is True
        response = client(author).patch(
            f"/api/v1/posts/{post.pk}/", {"is_spoiler": True}, format="json"
        )
        assert Post.objects.get(pk=post.pk).is_approved is True

    def test_markdown_spoiler_in_post_and_comment_bodies(self, sp):
        community, _, author, _, _ = sp
        api = client(author)
        response = create(api, community, body="a >!secret!< b")
        assert '<span class="spoiler">secret</span>' in response.data["body_html"]
        post_id = response.data["id"]
        comment = api.post(
            f"/api/v1/posts/{post_id}/comments/", {"body": "re >!reply!<"}, format="json"
        )
        assert '<span class="spoiler">reply</span>' in comment.data["body_html"]


@pytest.mark.django_db
class TestSpoilerOg:
    def test_og_page_hides_title_body_and_image(self, sp):
        community, _, author, _, _ = sp
        post = Post.objects.create(
            author=author,
            community=community,
            title="Secret title",
            body="Secret body",
            is_spoiler=True,
        )
        html = APIClient().get(f"/og/posts/{post.pk}/").content.decode()
        assert "Secret" not in html
        assert "og:image" not in html
        assert "Spoiler post in c/films" in html

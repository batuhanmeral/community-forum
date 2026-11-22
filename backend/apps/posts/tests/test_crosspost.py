import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.utils import timezone
from rest_framework.test import APIClient

from apps.communities.models import Community, Membership
from apps.moderation.models import ModAction
from apps.posts.models import Post

User = get_user_model()


@pytest.fixture
def world(db):
    owner = User.objects.create_user(username="owner", email="owner@example.com")
    sharer = User.objects.create_user(username="sharer", email="sharer@example.com")
    mod = User.objects.create_user(username="mod", email="mod@example.com")
    src = Community.objects.create(slug="src", name="Source", creator=owner)
    dst = Community.objects.create(slug="dst", name="Dest", creator=owner)
    for community in (src, dst):
        Membership.objects.create(user=sharer, community=community, role="member")
    Membership.objects.create(user=mod, community=dst, role="moderator")
    root = Post.objects.create(
        author=owner, community=src, kind="text", title="Original", body="Hello **world**"
    )
    return {"owner": owner, "sharer": sharer, "mod": mod, "src": src, "dst": dst, "root": root}


def client(user=None):
    api = APIClient()
    if user:
        api.force_authenticate(user)
    return api


def crosspost(user, post, community, **extra):
    return client(user).post(
        f"/api/v1/posts/{post.pk}/crosspost/", {"community": community.slug, **extra}, format="json"
    )


@pytest.mark.django_db
class TestCrosspost:
    def test_creates_linked_copy_in_target(self, world):
        w = world
        response = crosspost(w["sharer"], w["root"], w["dst"])
        assert response.status_code == 201
        data = response.data
        assert data["community"] == "dst"
        assert data["author"] == w["sharer"].pk
        assert (data["title"], data["body"]) == ("Original", "Hello **world**")
        assert "<strong>world</strong>" in data["body_html"]
        assert data["crosspost_from"] == {
            "id": w["root"].pk,
            "community": "src",
            "is_deleted": False,
        }
        assert Post.objects.get(pk=data["id"]).crosspost_parent_id == w["root"].pk

    def test_title_can_be_overridden(self, world):
        response = crosspost(world["sharer"], world["root"], world["dst"], title="Seen this?")
        assert response.data["title"] == "Seen this?"

    def test_chain_is_flattened_to_the_root(self, world):
        w = world
        first = crosspost(w["sharer"], w["root"], w["dst"]).data["id"]
        third = Community.objects.create(slug="third", name="Third", creator=w["owner"])
        Membership.objects.create(user=w["sharer"], community=third, role="member")
        again = crosspost(w["sharer"], Post.objects.get(pk=first), third)
        assert again.status_code == 201
        assert again.data["crosspost_from"]["id"] == w["root"].pk

    def test_needs_login_and_active_membership(self, world):
        w = world
        assert crosspost(None, w["root"], w["dst"]).status_code == 401
        outsider = User.objects.create_user(username="out", email="out@example.com")
        assert crosspost(outsider, w["root"], w["dst"]).status_code == 403
        Membership.objects.filter(user=w["sharer"], community=w["dst"]).update(is_banned=True)
        assert crosspost(w["sharer"], w["root"], w["dst"]).status_code == 403

    def test_unknown_target_or_missing_field(self, world):
        w = world
        response = client(w["sharer"]).post(
            f"/api/v1/posts/{w['root'].pk}/crosspost/", {"community": "nope"}, format="json"
        )
        assert response.status_code == 404
        response = client(w["sharer"]).post(
            f"/api/v1/posts/{w['root'].pk}/crosspost/", {}, format="json"
        )
        assert response.status_code == 400

    def test_duplicate_per_user_root_and_community(self, world):
        w = world
        first = crosspost(w["sharer"], w["root"], w["dst"])
        assert crosspost(w["sharer"], w["root"], w["dst"]).status_code == 400
        # Also when the second attempt goes through the crosspost.
        assert (
            crosspost(w["sharer"], Post.objects.get(pk=first.data["id"]), w["dst"]).status_code
            == 400
        )
        friend = User.objects.create_user(username="friend", email="friend@example.com")
        Membership.objects.create(user=friend, community=w["dst"], role="member")
        assert crosspost(friend, w["root"], w["dst"]).status_code == 201

    def test_can_repeat_after_deleting_own_crosspost(self, world):
        w = world
        first = crosspost(w["sharer"], w["root"], w["dst"])
        assert client(w["sharer"]).delete(f"/api/v1/posts/{first.data['id']}/").status_code == 204
        assert crosspost(w["sharer"], w["root"], w["dst"]).status_code == 201

    @pytest.mark.parametrize("state", ["held", "deleted"])
    def test_unavailable_source_is_refused(self, world, state):
        w = world
        if state == "held":
            Post.objects.filter(pk=w["root"].pk).update(is_approved=False)
        else:
            Post.objects.filter(pk=w["root"].pk).update(deleted_at=timezone.now())
        assert crosspost(w["sharer"], w["root"], w["dst"]).status_code in (400, 404)
        assert Post.objects.filter(crosspost_parent=w["root"]).count() == 0

    def test_source_crosspost_whose_root_is_gone_is_refused(self, world):
        w = world
        first = crosspost(w["sharer"], w["root"], w["dst"])
        Post.objects.filter(pk=w["root"].pk).update(deleted_at=timezone.now())
        third = Community.objects.create(slug="third", name="Third", creator=w["owner"])
        Membership.objects.create(user=w["sharer"], community=third, role="member")
        response = crosspost(w["sharer"], Post.objects.get(pk=first.data["id"]), third)
        assert response.status_code == 400

    def test_polls_cannot_be_crossposted(self, world):
        w = world
        Post.objects.filter(pk=w["root"].pk).update(kind="poll")
        assert crosspost(w["sharer"], w["root"], w["dst"]).status_code == 400

    def test_image_and_link_posts_carry_their_media(self, world):
        w = world
        link = Post.objects.create(
            author=w["owner"],
            community=w["src"],
            kind="link",
            title="L",
            url="https://example.com/x",
        )
        assert crosspost(w["sharer"], link, w["dst"]).data["url"] == "https://example.com/x"
        image = Post.objects.create(author=w["owner"], community=w["src"], kind="image", title="I")
        image.image.save("pic.png", ContentFile(b"x"), save=True)
        response = crosspost(w["sharer"], image, w["dst"])
        assert response.status_code == 201
        assert response.data["image"]

    def test_spoiler_flag_is_inherited(self, world):
        w = world
        Post.objects.filter(pk=w["root"].pk).update(is_spoiler=True)
        assert crosspost(w["sharer"], w["root"], w["dst"]).data["is_spoiler"] is True


@pytest.mark.django_db
class TestCrosspostNsfw:
    def test_nsfw_flag_is_inherited_and_cannot_be_cleared(self, world):
        w = world
        Post.objects.filter(pk=w["root"].pk).update(is_nsfw=True)
        User.objects.filter(pk=w["sharer"].pk).update(show_nsfw=True)
        w["sharer"].refresh_from_db()
        response = crosspost(w["sharer"], w["root"], w["dst"])
        assert response.status_code == 201
        assert response.data["is_nsfw"] is True
        patched = client(w["sharer"]).patch(
            f"/api/v1/posts/{response.data['id']}/", {"is_nsfw": False}, format="json"
        )
        assert patched.data["is_nsfw"] is True
        assert Post.objects.get(pk=response.data["id"]).is_nsfw is True

    @pytest.mark.parametrize("source", ["post", "community"])
    def test_viewer_without_nsfw_access_cannot_crosspost(self, world, source):
        w = world
        if source == "post":
            Post.objects.filter(pk=w["root"].pk).update(is_nsfw=True)
        else:
            Community.objects.filter(pk=w["src"].pk).update(is_nsfw=True)
        assert crosspost(w["sharer"], w["root"], w["dst"]).status_code == 404
        User.objects.filter(pk=w["sharer"].pk).update(show_nsfw=True)
        w["sharer"].refresh_from_db()
        response = crosspost(w["sharer"], w["root"], w["dst"])
        assert response.status_code == 201
        assert response.data["is_nsfw"] is True

    def test_nsfw_target_community_flags_the_copy(self, world):
        w = world
        Community.objects.filter(pk=w["dst"].pk).update(is_nsfw=True)
        assert crosspost(w["sharer"], w["root"], w["dst"]).data["is_nsfw"] is True


@pytest.mark.django_db
class TestCrosspostTargetRules:
    def test_target_approval_queue_holds_the_copy(self, world):
        w = world
        Community.objects.filter(pk=w["dst"].pk).update(requires_approval=True)
        held = crosspost(w["sharer"], w["root"], w["dst"])
        assert held.status_code == 201
        assert held.data["is_approved"] is False
        # Moderators of the target bypass the queue, like for normal posts.
        w["root2"] = Post.objects.create(author=w["owner"], community=w["src"], title="B", body="b")
        assert crosspost(w["mod"], w["root2"], w["dst"]).data["is_approved"] is True

    def test_target_automod_keyword_holds_and_logs(self, world):
        w = world
        Community.objects.filter(pk=w["dst"].pk).update(banned_keywords="world")
        response = crosspost(w["sharer"], w["root"], w["dst"])
        assert response.data["is_approved"] is False
        assert ModAction.objects.filter(
            community=w["dst"], action=ModAction.Action.AUTOMOD_HOLD
        ).exists()

    def test_removed_by_a_moderator_counts_as_unavailable(self, world):
        w = world
        Membership.objects.create(user=w["mod"], community=w["src"], role="moderator")
        assert client(w["mod"]).delete(f"/api/v1/posts/{w['root'].pk}/").status_code == 204
        assert crosspost(w["sharer"], w["root"], w["dst"]).status_code in (400, 404)


@pytest.mark.django_db
class TestCrosspostPlaceholderAndEdits:
    def test_source_removal_masks_every_copy_without_leaking(self, world):
        w = world
        Post.objects.filter(pk=w["root"].pk).update(url="")
        copy = crosspost(w["sharer"], w["root"], w["dst"]).data["id"]
        Post.objects.filter(pk=w["root"].pk).update(deleted_at=timezone.now())
        for url in (
            f"/api/v1/posts/{copy}/",
            "/api/v1/communities/dst/posts/",
            "/api/v1/feed/?scope=all",
        ):
            payload = client().get(url).data
            row = payload["results"][0] if "results" in payload else payload
            assert row["crosspost_from"]["is_deleted"] is True
            assert row["title"] == "[deleted]"
            assert row["body"] == "[deleted]"
            assert row["body_html"] == "<p>[deleted]</p>"
            assert row["url"] == "" and row["image"] is None
            assert "Original" not in str(row) and "world" not in str(row)

    def test_held_source_also_masks(self, world):
        w = world
        copy = crosspost(w["sharer"], w["root"], w["dst"]).data["id"]
        Post.objects.filter(pk=w["root"].pk).update(is_approved=False)
        row = client().get(f"/api/v1/posts/{copy}/").data
        assert row["body"] == "[deleted]"
        assert row["crosspost_from"]["is_deleted"] is True

    def test_hard_deleted_source_leaves_a_deleted_placeholder(self, world):
        """Spec: if the source is deleted the copy is a "[deleted]" placeholder; nothing leaks."""
        w = world
        copy = crosspost(w["sharer"], w["root"], w["dst"]).data["id"]
        w["root"].delete()
        post = Post.objects.get(pk=copy)
        assert post.crosspost_parent_id is None
        assert post.deleted_at is not None
        assert "world" not in post.body + post.body_html and post.title == "[deleted]"
        data = client(w["sharer"]).get(f"/api/v1/posts/{copy}/").data
        assert data["title"] == "[deleted]" and data["is_deleted"] is True
        # Not a moderator removal: the copy reads "[deleted]", never "[removed]".
        assert data["body"] == "[deleted]" and post.deleted_by_id == post.author_id
        assert "world" not in data["body"] + data["body_html"]
        assert copy not in [
            r["id"] for r in client().get("/api/v1/feed/?scope=all").data["results"]
        ]

    def test_content_is_locked_but_title_is_editable(self, world):
        w = world
        copy = crosspost(w["sharer"], w["root"], w["dst"]).data["id"]
        api = client(w["sharer"])
        assert (
            api.patch(f"/api/v1/posts/{copy}/", {"body": "mine"}, format="json").status_code == 400
        )
        assert (
            api.patch(f"/api/v1/posts/{copy}/", {"title": "New"}, format="json").data["title"]
            == "New"
        )

    def test_votes_and_comments_are_separate(self, world):
        w = world
        copy = crosspost(w["sharer"], w["root"], w["dst"]).data
        assert copy["score"] == 0 and copy["comment_count"] == 0
        assert copy["id"] != w["root"].pk

    def test_feed_query_count_does_not_grow_with_crossposts(self, world):
        w = world
        crosspost(w["sharer"], w["root"], w["dst"])
        api = client(w["sharer"])
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as small:
            assert api.get("/api/v1/feed/?scope=all").status_code == 200
        for i in range(5):
            extra = Post.objects.create(
                author=w["owner"], community=w["src"], title=f"E{i}", body="b"
            )
            third = Community.objects.create(slug=f"t{i}", name=f"T{i}", creator=w["owner"])
            Membership.objects.create(user=w["sharer"], community=third, role="member")
            assert crosspost(w["sharer"], extra, third).status_code == 201
        with CaptureQueriesContext(connection) as large:
            response = api.get("/api/v1/feed/?scope=all")
        assert len(response.data["results"]) == 12  # six originals and six copies
        assert len(large) == len(small) > 0


def _unavailable(root, how):
    if how == "deleted":
        Post.objects.filter(pk=root.pk).update(deleted_at=timezone.now())
    else:
        Post.objects.filter(pk=root.pk).update(is_approved=False)


@pytest.mark.django_db
class TestUnavailableRootLeaks:
    @pytest.mark.parametrize("how", ["deleted", "held"])
    def test_og_page_masks_the_copy(self, world, how):
        from django.core.cache import cache
        from django.urls import reverse

        w = world
        Post.objects.filter(pk=w["root"].pk).update(title="Secret title", body="Secret body")
        copy = Post.objects.create(
            author=w["sharer"],
            community=w["dst"],
            title="Secret title",
            body="Secret body",
            crosspost_parent=w["root"],
        )
        _unavailable(w["root"], how)
        cache.clear()
        html = client().get(reverse("og:og-post", args=[copy.pk])).content.decode()
        assert "Secret" not in html
        assert "[deleted]" in html

    @pytest.mark.parametrize("how", ["deleted", "held"])
    def test_search_does_not_match_the_copied_text(self, world, how):
        w = world
        copy = crosspost(w["sharer"], w["root"], w["dst"]).data["id"]
        _unavailable(w["root"], how)
        ids = [r["id"] for r in client().get("/api/v1/search/?q=world&type=post").data["results"]]
        assert copy not in ids


def _flag_root_nsfw(w, where):
    if where == "post":
        Post.objects.filter(pk=w["root"].pk).update(is_nsfw=True)
    else:
        Community.objects.filter(pk=w["src"].pk).update(is_nsfw=True)


@pytest.mark.django_db
class TestFlagsFollowTheOriginal:
    @pytest.mark.parametrize("where", ["post", "community"])
    def test_later_nsfw_original_hides_existing_copies(self, world, where):
        from django.core.cache import cache

        w = world
        copy = crosspost(w["sharer"], w["root"], w["dst"]).data["id"]
        _flag_root_nsfw(w, where)
        cache.clear()
        anon = client()

        def ids(url):
            return [r["id"] for r in anon.get(url).data["results"]]

        assert copy not in ids("/api/v1/feed/?scope=all")
        # The community page lists NSFW posts on purpose; the flag makes the client blur them.
        listed = anon.get("/api/v1/communities/dst/posts/").data["results"]
        assert [r["is_nsfw"] for r in listed if r["id"] == copy] == [True]
        assert copy not in ids("/api/v1/trending/posts/")
        assert copy not in ids("/api/v1/search/?q=world&type=post")
        atom = anon.get("/api/v1/communities/dst/feed.atom").content
        assert f"/posts/{copy}".encode() not in atom
        data = client(w["sharer"]).get(f"/api/v1/posts/{copy}/").data
        assert data["is_nsfw"] is True

    def test_later_spoiler_original_hides_copy_content(self, world):
        from django.core.cache import cache
        from django.urls import reverse

        w = world
        copy = crosspost(w["sharer"], w["root"], w["dst"]).data["id"]
        Post.objects.filter(pk=w["root"].pk).update(is_spoiler=True)
        cache.clear()
        anon = client()
        assert anon.get(f"/api/v1/posts/{copy}/").data["is_spoiler"] is True
        atom = anon.get("/api/v1/communities/dst/feed.atom").content
        assert f"/posts/{copy}".encode() in atom
        assert b"world" not in atom
        og = anon.get(reverse("og:og-post", args=[copy])).content.decode()
        assert "Original" not in og and "world" not in og


@pytest.mark.django_db
class TestCrosspostRefusals:
    def test_banned_in_the_source_community(self, world):
        w = world
        Membership.objects.filter(user=w["sharer"], community=w["src"]).update(is_banned=True)
        assert crosspost(w["sharer"], w["root"], w["dst"]).status_code == 403
        assert not Post.objects.filter(crosspost_parent=w["root"]).exists()

    def test_into_the_originals_own_community(self, world):
        w = world
        assert crosspost(w["sharer"], w["root"], w["src"]).status_code == 400
        copy = crosspost(w["sharer"], w["root"], w["dst"]).data["id"]
        # Re-sharing the copy resolves to the root, whose community is src.
        assert crosspost(w["sharer"], Post.objects.get(pk=copy), w["src"]).status_code == 400

    @pytest.mark.parametrize("direction", ["author_blocks", "sharer_blocks"])
    def test_blocked_author(self, world, direction):
        from apps.social.models import Block

        w = world
        a, b = (
            (w["owner"], w["sharer"]) if direction == "author_blocks" else (w["sharer"], w["owner"])
        )
        Block.objects.create(blocker=a, blocked=b)
        assert crosspost(w["sharer"], w["root"], w["dst"]).status_code == 403

    def test_suspended_author(self, world):
        w = world
        User.objects.filter(pk=w["owner"].pk).update(is_active=False)
        assert crosspost(w["sharer"], w["root"], w["dst"]).status_code == 400


@pytest.mark.django_db
def test_a_moderator_removed_copy_keeps_its_removal_when_the_original_goes(world):
    w = world
    copy = crosspost(w["sharer"], w["root"], w["dst"]).data["id"]
    Post.objects.filter(pk=copy).update(deleted_at=timezone.now(), deleted_by=w["mod"])
    w["root"].delete()
    assert Post.objects.get(pk=copy).deleted_by_id == w["mod"].pk


@pytest.mark.django_db
class TestOriginalStateReachesCopies:
    def test_resharing_a_copy_while_banned_only_where_the_original_lives(self, world):
        w = world
        copy = Post.objects.get(pk=crosspost(w["sharer"], w["root"], w["dst"]).data["id"])
        third = Community.objects.create(slug="third", name="Third", creator=w["owner"])
        Membership.objects.create(user=w["sharer"], community=third, role="member")
        Membership.objects.filter(user=w["sharer"], community=w["src"]).update(is_banned=True)
        assert crosspost(w["sharer"], copy, third).status_code == 403

    def test_og_of_a_copy_whose_original_turned_nsfw(self, world):
        from django.core.cache import cache
        from django.urls import reverse

        w = world
        copy = crosspost(w["sharer"], w["root"], w["dst"]).data["id"]
        Post.objects.filter(pk=w["root"].pk).update(is_nsfw=True)
        cache.clear()
        html = client().get(reverse("og:og-post", args=[copy])).content.decode()
        assert "NSFW post" in html and "Original" not in html

    def test_comments_feed_of_a_copy_whose_original_turned_spoiler(self, world):
        from django.core.cache import cache

        from apps.comments.models import Comment

        w = world
        copy = crosspost(w["sharer"], w["root"], w["dst"]).data["id"]
        Comment.objects.create(post_id=copy, author=w["owner"], body="the twist is obvious")
        Post.objects.filter(pk=w["root"].pk).update(is_spoiler=True)
        cache.clear()
        feed = client().get(f"/api/v1/posts/{copy}/comments.atom").content
        assert b"<entry>" in feed and b"twist" not in feed

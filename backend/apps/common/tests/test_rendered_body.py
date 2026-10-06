import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.comments.models import Comment
from apps.common.rendered_body import backfill_body_html
from apps.communities.models import Community
from apps.posts.models import Post

User = get_user_model()


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="alice", email="a@x.com", password="x")


@pytest.fixture
def community(alice):
    return Community.objects.create(slug="py", name="Python", creator=alice)


@pytest.fixture
def post(alice, community):
    return Post.objects.create(
        author=alice, community=community, kind="text", title="t", body="**v1**"
    )


@pytest.fixture
def comment(alice, post):
    return Comment.objects.create(post=post, author=alice, body="**c1**")


@pytest.mark.django_db
class TestStoredOnWrite:
    def test_create_stores_rendered_html(self, post, comment):
        post.refresh_from_db()
        comment.refresh_from_db()
        assert "<strong>v1</strong>" in post.body_html
        assert "<strong>c1</strong>" in comment.body_html

    def test_save_with_body_in_update_fields_persists_html(self, post):
        post.body = "**v2**"
        post.save(update_fields=["body"])
        post.refresh_from_db()
        assert "<strong>v2</strong>" in post.body_html

    def test_post_edit_rerenders(self, api, alice, post):
        api.force_authenticate(alice)
        resp = api.patch(
            reverse("api_v1:posts:post-detail", args=[post.id]), {"body": "**v2**"}, format="json"
        )
        assert resp.status_code == 200
        assert "<strong>v2</strong>" in resp.data["body_html"]
        post.refresh_from_db()
        assert "<strong>v2</strong>" in post.body_html

    def test_comment_edit_rerenders(self, api, alice, comment):
        api.force_authenticate(alice)
        resp = api.patch(
            reverse("api_v1:comments:comment-detail", args=[comment.id]),
            {"body": "**c2**"},
            format="json",
        )
        assert resp.status_code == 200
        comment.refresh_from_db()
        assert "<strong>c2</strong>" in comment.body_html


@pytest.mark.django_db
class TestReadsUseStoredHtml:
    def test_post_detail_returns_stored_html(self, api, post):
        Post.objects.filter(pk=post.pk).update(body_html="<p>stored</p>")
        resp = api.get(reverse("api_v1:posts:post-detail", args=[post.id]))
        assert resp.data["body_html"] == "<p>stored</p>"

    def test_comment_list_returns_stored_html(self, api, post, comment):
        Comment.objects.filter(pk=comment.pk).update(body_html="<p>stored</p>")
        resp = api.get(reverse("api_v1:post-comments:post-comments", args=[post.id]))
        assert resp.data["results"][0]["body_html"] == "<p>stored</p>"

    def test_deleted_comment_never_returns_stored_html(self, api, alice, post, comment):
        Comment.objects.filter(pk=comment.pk).update(deleted_at=timezone.now(), deleted_by=alice)
        resp = api.get(reverse("api_v1:post-comments:post-comments", args=[post.id]))
        assert resp.data["results"][0]["body_html"] == "<p>[deleted]</p>"


@pytest.mark.django_db
class TestBackfill:
    def test_fills_rows_that_predate_the_column(self, alice, community):
        for i in range(3):
            Post.objects.create(
                author=alice, community=community, kind="text", title="t", body=f"**p{i}**"
            )
        Post.objects.update(body_html="")
        backfill_body_html(Post, batch_size=2)
        for p in Post.objects.all():
            assert f"<strong>{p.body[2:4]}</strong>" in p.body_html

    def test_fills_comments(self, post, comment):
        Comment.objects.update(body_html="")
        backfill_body_html(Comment)
        comment.refresh_from_db()
        assert "<strong>c1</strong>" in comment.body_html

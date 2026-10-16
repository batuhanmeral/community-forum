import importlib

import django.apps
import pytest
from django.contrib.auth import get_user_model

from apps.comments.models import Comment
from apps.communities.models import Community
from apps.posts.models import Post

User = get_user_model()
LINK_BODY = "[a](https://x.com)"


@pytest.fixture
def post(db):
    alice = User.objects.create_user(username="alice", email="a@x.com", password="x")
    community = Community.objects.create(slug="py", name="Python", creator=alice)
    return Post.objects.create(
        author=alice, community=community, kind="text", title="t", body=LINK_BODY
    )


@pytest.fixture
def comment(post):
    return Comment.objects.create(post=post, author=post.author, body=LINK_BODY)


def _run_backfill_on_stale_row(row, migration):
    type(row).objects.filter(pk=row.pk).update(body_html="<p>stale</p>")
    importlib.import_module(migration).backfill(django.apps.apps, None)
    row.refresh_from_db()
    return row.body_html


def test_post_migration_rerenders_links(post):
    body_html = _run_backfill_on_stale_row(post, "apps.posts.migrations.0008_rerender_links")
    assert "noreferrer" in body_html


def test_comment_migration_rerenders_links(comment):
    body_html = _run_backfill_on_stale_row(comment, "apps.comments.migrations.0005_rerender_links")
    assert "noreferrer" in body_html

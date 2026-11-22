import xml.etree.ElementTree as ET

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from apps.comments.models import Comment
from apps.communities.models import Community
from apps.posts.models import Post
from apps.votes.models import Vote  # noqa: F401  (registers vote signals for score ordering)

User = get_user_model()
NS = {"a": "http://www.w3.org/2005/Atom"}


@pytest.fixture
def aw(db):
    author = User.objects.create_user(username="author", email="a@example.com")
    other = User.objects.create_user(username="other", email="o@example.com")
    community = Community.objects.create(slug="py", name="Py", creator=author, description="d")
    post = Post.objects.create(
        author=author, community=community, title="Hello", body="**bold** text"
    )
    return {"author": author, "other": other, "community": community, "post": post}


def get(url, **headers):
    return APIClient().get(url, **headers)


def parse(response):
    assert response.status_code == 200, response.content
    assert response["Content-Type"].startswith("application/atom+xml")
    return ET.fromstring(response.content)


def entries(root):
    return root.findall("a:entry", NS)


def titles(root):
    return [e.find("a:title", NS).text for e in entries(root)]


@pytest.mark.django_db
class TestCommunityFeed:
    URL = "/api/v1/communities/py/feed.atom"

    def test_valid_atom_with_content_and_links(self, aw):
        root = parse(get(self.URL))
        assert root.find("a:title", NS).text
        entry = entries(root)[0]
        assert entry.find("a:title", NS).text == "Hello"
        link = entry.find("a:link", NS).get("href")
        assert link.endswith(f"/posts/{aw['post'].pk}")
        assert "<strong>bold</strong>" in entry.find("a:summary", NS).text
        assert entry.find("a:author/a:name", NS).text == "author"

    def test_xml_special_characters_are_escaped_and_control_chars_dropped(self, aw):
        Post.objects.create(
            author=aw["author"],
            community=aw["community"],
            title='<script>alert("x")</script> & \x08 more',
            body="a < b & c \x0b ]]> end",
        )
        response = get(self.URL)
        root = parse(response)
        assert b"<script>" not in response.content
        assert '<script>alert("x")</script> &  more' in titles(root)

    def test_excludes_nsfw_held_deleted_and_masked_crossposts(self, aw):
        c = aw["community"]
        a = aw["author"]
        Post.objects.create(author=a, community=c, title="nsfw", is_nsfw=True)
        Post.objects.create(author=a, community=c, title="held", is_approved=False)
        Post.objects.create(author=a, community=c, title="gone", deleted_at=timezone.now())
        other = Community.objects.create(slug="src", name="Src", creator=a)
        root = Post.objects.create(author=a, community=other, title="root", body="r")
        Post.objects.create(author=a, community=c, title="copy", crosspost_parent=root)
        assert sorted(titles(parse(get(self.URL)))) == ["Hello", "copy"]
        Post.objects.filter(pk=root.pk).update(deleted_at=timezone.now())
        cache.clear()
        assert titles(parse(get(self.URL))) == ["Hello"]

    def test_nsfw_community_and_unknown_slug_are_404(self, aw):
        Community.objects.filter(pk=aw["community"].pk).update(is_nsfw=True)
        assert get(self.URL).status_code == 404
        assert get("/api/v1/communities/nope/feed.atom").status_code == 404

    def test_spoiler_posts_carry_no_body(self, aw):
        Post.objects.create(
            author=aw["author"],
            community=aw["community"],
            title="Spoiler!",
            body="he dies",
            is_spoiler=True,
        )
        Post.objects.create(
            author=aw["author"],
            community=aw["community"],
            title="Inline",
            body="x >!he dies!< y",
        )
        response = get(self.URL)
        assert b"he dies" not in response.content
        root = parse(response)
        by_title = {e.find("a:title", NS).text: e for e in entries(root)}
        assert by_title["Spoiler!"].find("a:summary", NS) is None
        assert by_title["Inline"].find("a:summary", NS) is None
        assert by_title["Spoiler!"].find("a:link", NS) is not None

    def test_sort_new_top_and_time_window(self, aw):
        c, a = aw["community"], aw["author"]
        older = Post.objects.create(author=a, community=c, title="older", body="o")
        Post.objects.filter(pk=older.pk).update(
            created_at=timezone.now() - timezone.timedelta(days=40)
        )
        Vote.objects.create(
            user=aw["other"], content_type_id=_ct(Post), object_id=older.pk, value=1
        )
        assert titles(parse(get(self.URL + "?sort=new")))[0] == "Hello"
        assert titles(parse(get(self.URL + "?sort=top")))[0] == "older"
        assert titles(parse(get(self.URL + "?sort=top&t=week"))) == ["Hello"]
        assert get(self.URL + "?sort=bogus").status_code == 200

    def test_page_size_is_capped_with_a_next_link(self, aw):
        c, a = aw["community"], aw["author"]
        Post.objects.bulk_create(
            [Post(author=a, community=c, title=f"P{i}", body="b") for i in range(60)]
        )
        root = parse(get(self.URL))
        assert len(entries(root)) == 50
        rels = {link.get("rel"): link.get("href") for link in root.findall("a:link", NS)}
        assert "page=2" in rels["next"]
        second = parse(get(self.URL + "?page=2"))
        assert len(entries(second)) == 11
        assert "next" not in {link.get("rel") for link in second.findall("a:link", NS)}
        assert get(self.URL + "?page=abc").status_code == 400

    def test_next_link_with_other_params_stays_valid_xml(self, aw):
        from urllib.parse import parse_qs, urlsplit

        c, a = aw["community"], aw["author"]
        Post.objects.bulk_create(
            [Post(author=a, community=c, title=f"P{i}", body="b") for i in range(50)]
        )
        root = parse(get(self.URL + "?sort=top&t=all"))
        assert len(entries(root)) == 50
        rels = {link.get("rel"): link.get("href") for link in root.findall("a:link", NS)}
        assert parse_qs(urlsplit(rels["next"]).query) == {
            "sort": ["top"],
            "t": ["all"],
            "page": ["2"],
        }

    def test_empty_feed_is_still_valid(self, aw):
        Post.objects.all().delete()
        root = parse(get(self.URL))
        assert entries(root) == []
        assert root.find("a:updated", NS) is not None


@pytest.mark.django_db
class TestUserAndCommentFeeds:
    def test_user_feed_lists_only_public_visible_posts(self, aw):
        a = aw["author"]
        hidden = Community.objects.create(slug="adult", name="Adult", creator=a, is_nsfw=True)
        Post.objects.create(author=a, community=hidden, title="adult post")
        Post.objects.create(author=a, community=aw["community"], title="held", is_approved=False)
        assert titles(parse(get("/api/v1/users/author/posts.atom"))) == ["Hello"]
        assert get("/api/v1/users/nobody/posts.atom").status_code == 404
        User.objects.filter(pk=a.pk).update(is_active=False)
        assert get("/api/v1/users/author/posts.atom").status_code == 404

    def test_comment_feed(self, aw):
        post = aw["post"]
        Comment.objects.create(post=post, author=aw["other"], body="nice <b>one</b>")
        Comment.objects.create(
            post=post, author=aw["other"], body="removed", deleted_at=timezone.now()
        )
        root = parse(get(f"/api/v1/posts/{post.pk}/comments.atom"))
        assert len(entries(root)) == 1
        entry = entries(root)[0]
        assert "u/other" in entry.find("a:title", NS).text
        assert f"/posts/{post.pk}#comment-" in entry.find("a:link", NS).get("href")
        assert "<b>one</b>" in entry.find("a:summary", NS).text

    @pytest.mark.parametrize("state", ["nsfw", "nsfw_community", "held", "deleted"])
    def test_comment_feed_of_unavailable_posts_is_404(self, aw, state):
        post = aw["post"]
        if state == "nsfw":
            Post.objects.filter(pk=post.pk).update(is_nsfw=True)
        elif state == "nsfw_community":
            Community.objects.filter(pk=aw["community"].pk).update(is_nsfw=True)
        elif state == "held":
            Post.objects.filter(pk=post.pk).update(is_approved=False)
        else:
            Post.objects.filter(pk=post.pk).update(deleted_at=timezone.now())
        assert get(f"/api/v1/posts/{post.pk}/comments.atom").status_code == 404

    def test_comments_of_a_spoiler_post_have_no_body(self, aw):
        post = aw["post"]
        Post.objects.filter(pk=post.pk).update(is_spoiler=True)
        Comment.objects.create(post=post, author=aw["other"], body="the butler did it")
        response = get(f"/api/v1/posts/{post.pk}/comments.atom")
        assert b"butler" not in response.content
        assert len(entries(parse(response))) == 1

    def test_inline_spoiler_in_a_comment_hides_the_body(self, aw):
        Comment.objects.create(post=aw["post"], author=aw["other"], body="ok >!secret!< ok")
        assert b"secret" not in get(f"/api/v1/posts/{aw['post'].pk}/comments.atom").content

    def test_deleted_comment_author_shows_as_deleted(self, aw):
        Comment.objects.create(post=aw["post"], author=aw["other"], body="hi")
        User.objects.filter(pk=aw["other"].pk).update(is_active=False)
        response = get(f"/api/v1/posts/{aw['post'].pk}/comments.atom")
        assert b"other" not in response.content
        assert b"[deleted]" in response.content


@pytest.mark.django_db
class TestCachingAndThrottle:
    URL = "/api/v1/communities/py/feed.atom"

    @pytest.mark.parametrize("kind", ["community", "user", "comments"])
    def test_a_cache_hit_does_not_query_the_rows(self, aw, kind):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        Comment.objects.create(post=aw["post"], author=aw["other"], body="hi")
        url = {
            "community": self.URL,
            "user": "/api/v1/users/author/posts.atom",
            "comments": f"/api/v1/posts/{aw['post'].pk}/comments.atom",
        }[kind]
        assert get(url).status_code == 200
        with CaptureQueriesContext(connection) as ctx:
            assert get(url).status_code == 200
        table = "comments_comment" if kind == "comments" else "posts_post"
        rows = [q["sql"] for q in ctx.captured_queries if f'FROM "{table}"' in q["sql"]]
        assert rows == [], rows

    def test_etag_and_last_modified_conditional_gets(self, aw):
        first = get(self.URL)
        etag, modified = first["ETag"], first["Last-Modified"]
        assert etag and modified
        assert first["Cache-Control"].startswith("public")
        assert get(self.URL, HTTP_IF_NONE_MATCH=etag).status_code == 304
        assert get(self.URL, HTTP_IF_MODIFIED_SINCE=modified).status_code == 304
        assert get(self.URL, HTTP_IF_NONE_MATCH='"other"').status_code == 200

    def test_short_server_side_cache_then_refresh(self, aw):
        first = get(self.URL)
        Post.objects.create(author=aw["author"], community=aw["community"], title="Later")
        assert get(self.URL).content == first.content
        cache.clear()
        changed = get(self.URL)
        assert b"Later" in changed.content
        assert changed["ETag"] != first["ETag"]

    def test_anonymous_throttle(self, aw, settings):
        from rest_framework.throttling import AnonRateThrottle

        AnonRateThrottle.THROTTLE_RATES = {**AnonRateThrottle.THROTTLE_RATES, "anon": "3/min"}
        try:
            codes = [get(self.URL).status_code for _ in range(5)]
        finally:
            AnonRateThrottle.THROTTLE_RATES = {**AnonRateThrottle.THROTTLE_RATES, "anon": "60/min"}
        assert codes[:3] == [200, 200, 200] and 429 in codes[3:]

    def test_query_count_is_flat(self, aw):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as small:
            get(self.URL)
        cache.clear()
        Post.objects.bulk_create(
            [Post(author=aw["author"], community=aw["community"], title=f"P{i}") for i in range(20)]
        )
        with CaptureQueriesContext(connection) as large:
            get(self.URL)
        assert len(large) == len(small)


@pytest.mark.django_db
class TestDiscoveryLinks:
    def test_og_pages_advertise_the_matching_feed(self, aw):
        api = APIClient()
        community = api.get("/og/c/py/").content.decode()
        assert 'rel="alternate" type="application/atom+xml"' in community
        assert "/api/v1/communities/py/feed.atom" in community
        user = api.get("/og/u/author/").content.decode()
        assert "/api/v1/users/author/posts.atom" in user
        post = api.get(f"/og/posts/{aw['post'].pk}/").content.decode()
        assert f"/api/v1/posts/{aw['post'].pk}/comments.atom" in post

    def test_nsfw_and_spoiler_og_pages_advertise_no_feed(self, aw):
        Post.objects.filter(pk=aw["post"].pk).update(is_spoiler=True)
        assert "atom+xml" not in APIClient().get(f"/og/posts/{aw['post'].pk}/").content.decode()
        Community.objects.filter(pk=aw["community"].pk).update(is_nsfw=True)
        assert "atom+xml" not in APIClient().get("/og/c/py/").content.decode()


def _ct(model):
    from django.contrib.contenttypes.models import ContentType

    return ContentType.objects.get_for_model(model).pk

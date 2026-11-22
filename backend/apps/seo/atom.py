"""Public Atom feeds for communities, users and comment threads.

Feeds are anonymous documents: they never contain NSFW, held, removed or deleted content,
and spoiler bodies are left out entirely (title and link only). Output is identical for every
viewer, so it is cached briefly and served with ETag / Last-Modified validators.
"""

import hashlib
import re
from datetime import UTC, datetime
from urllib.parse import urlencode
from xml.sax.saxutils import quoteattr

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.cache import get_conditional_response
from django.utils.feedgenerator import Atom1Feed
from django.utils.http import http_date, quote_etag
from rest_framework import permissions
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView

from apps.comments.models import Comment
from apps.comments.views import _annotate_score as _annotate_comment_score
from apps.communities.models import Community
from apps.posts.models import Post
from apps.posts.services import effective_spoiler, nsfw_q, unavailable_root_q
from apps.posts.views import _annotate_score, _apply_sort, _apply_time_window

User = get_user_model()

SITE_NAME = "Nexus"
PAGE_SIZE = 50
CACHE_SECONDS = 60
CONTENT_TYPE = "application/atom+xml; charset=utf-8"
# XML 1.0 forbids these control characters; one of them would make the whole feed unparseable.
_XML_ILLEGAL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")
_SPOILER_MARK = 'class="spoiler"'
SORTS = ("new", "top")


def _clean(text: str) -> str:
    return _XML_ILLEGAL.sub("", text)


def feed_links(request) -> dict:
    """Absolute Atom URLs by kind, for the discovery <link> tags on Open Graph pages."""
    build = request.build_absolute_uri
    return {
        "community": lambda slug: build(f"/api/v1/communities/{slug}/feed.atom"),
        "user": lambda name: build(f"/api/v1/users/{name}/posts.atom"),
        "post": lambda pk: build(f"/api/v1/posts/{pk}/comments.atom"),
    }


def _hides_body(body_html: str) -> bool:
    # Only the `>!..!<` rule can produce this attribute, so its presence means a spoiler span.
    return _SPOILER_MARK in body_html


def _public_posts():
    return (
        Post.objects.filter(is_approved=True, deleted_at__isnull=True, author__is_active=True)
        .exclude(nsfw_q())
        # A copy of a post that is gone or held is masked in the API; the feed just skips it.
        .exclude(unavailable_root_q())
        .select_related("author", "community", "crosspost_parent")
    )


class _Feed(Atom1Feed):
    def latest_post_date(self):
        return super().latest_post_date() or self.feed.get("fallback_updated")


def _page(request) -> int:
    raw = request.query_params.get("page", "1")
    if not raw.isdigit() or not 1 <= int(raw) <= 10_000:
        raise ValidationError({"page": "Must be a positive integer."})
    return int(raw)


def _sort_and_window(request):
    sort = request.query_params.get("sort", "new")
    return (sort if sort in SORTS else "new"), request.query_params.get("t")


def _respond(request, build):
    """Serve a feed from a 60 s cache, honouring If-None-Match / If-Modified-Since."""
    key = "atom:" + hashlib.sha256(request.get_full_path().encode()).hexdigest()
    cached = cache.get(key)
    if cached is None:
        body, last_modified = build()
        cached = (body, f'"{hashlib.sha256(body).hexdigest()[:32]}"', last_modified)
        cache.set(key, cached, CACHE_SECONDS)
    body, etag, last_modified = cached
    not_modified = get_conditional_response(
        request, etag=etag, last_modified=int(last_modified.timestamp())
    )
    response = not_modified or HttpResponse(body, content_type=CONTENT_TYPE)
    response["ETag"] = quote_etag(etag.strip('"'))
    response["Last-Modified"] = http_date(last_modified.timestamp())
    response["Cache-Control"] = f"public, max-age={CACHE_SECONDS}"
    return response


def _build_feed(request, *, title, subtitle, link, feed_url, items, fallback, has_next, page):
    feed = _Feed(
        title=_clean(title),
        link=link,
        description=_clean(subtitle) or title,
        feed_url=feed_url,
        language="en",
        fallback_updated=fallback,
    )
    for item in items:
        feed.add_item(**item)
    body = feed.writeString("utf-8").encode("utf-8")
    if has_next:
        # Django's Atom writer has no paging links, so add the standard rel="next" ourselves.
        params = request.query_params.copy()
        params["page"] = str(page + 1)
        href = request.build_absolute_uri(request.path) + "?" + urlencode(params)
        marker = b"<updated>" if b"<updated>" in body else b"<subtitle"
        # quoteattr escapes "&" between query params; a raw one makes the document unparseable.
        # nosemgrep: python.django.security.injection.raw-html-format.raw-html-format -- Atom XML, not HTML; href is quoteattr-escaped
        link = f'<link href={quoteattr(href)} rel="next"></link>'
        body = body.replace(marker, link.encode() + marker, 1)
    latest = feed.latest_post_date() or fallback
    return body, latest


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _post_item(post: Post) -> dict:
    link = f"{settings.FRONTEND_URL}/posts/{post.pk}"
    show_body = (
        not effective_spoiler(post) and not _hides_body(post.body_html) and bool(post.body_html)
    )
    return {
        "title": _clean(post.title),
        "link": link,
        "description": _clean(post.body_html) if show_body else None,
        "unique_id": link,
        "author_name": post.author.username,
        "pubdate": _aware(post.created_at),
        "updateddate": _aware(post.edited_at or post.created_at),
    }


def _post_feed(request, qs, *, title, subtitle, path, link, fallback):
    sort, window = _sort_and_window(request)
    page = _page(request)
    qs = _apply_sort(_apply_time_window(_annotate_score(qs), window), sort)

    def build():
        # Rows are read only on a cache miss. One extra row tells us whether a next page
        # exists without a COUNT query.
        rows = list(qs[(page - 1) * PAGE_SIZE : page * PAGE_SIZE + 1])
        return _build_feed(
            request,
            title=title,
            subtitle=subtitle,
            link=link,
            feed_url=request.build_absolute_uri(path),
            items=[_post_item(p) for p in rows[:PAGE_SIZE]],
            fallback=fallback,
            has_next=len(rows) > PAGE_SIZE,
            page=page,
        )

    return _respond(request, build)


class _AtomView(APIView):
    permission_classes = (permissions.AllowAny,)
    # Output never depends on who asks, so skip auth work and let anonymous throttling apply.
    authentication_classes = ()


class CommunityAtomView(_AtomView):
    def get(self, request, slug):
        community = get_object_or_404(Community, slug=slug, is_nsfw=False)
        return _post_feed(
            request,
            _public_posts().filter(community=community),
            title=f"c/{community.slug} on {SITE_NAME}",
            subtitle=community.description,
            path=request.path,
            link=f"{settings.FRONTEND_URL}/c/{community.slug}",
            fallback=_aware(community.created_at),
        )


class UserAtomView(_AtomView):
    def get(self, request, username):
        user = get_object_or_404(User, username__iexact=username, is_active=True)
        return _post_feed(
            request,
            _public_posts().filter(author=user),
            title=f"u/{user.username} on {SITE_NAME}",
            subtitle="",
            path=request.path,
            link=f"{settings.FRONTEND_URL}/u/{user.username}",
            fallback=_aware(user.date_joined),
        )


class PostCommentsAtomView(_AtomView):
    def get(self, request, pk):
        post = get_object_or_404(_public_posts(), pk=pk)
        sort, window = _sort_and_window(request)
        page = _page(request)
        comments = _annotate_comment_score(
            Comment.objects.filter(post=post, deleted_at__isnull=True).select_related("author")
        )
        comments = _apply_time_window(comments, window)
        comments = (
            comments.order_by("-score", "-created_at", "id")
            if sort == "top"
            else comments.order_by("-created_at", "id")
        )
        post_link = f"{settings.FRONTEND_URL}/posts/{post.pk}"

        def item(comment: Comment) -> dict:
            link = f"{post_link}#comment-{comment.pk}"
            name = comment.author.username if comment.author.is_active else "[deleted]"
            show_body = not effective_spoiler(post) and not _hides_body(comment.body_html)
            return {
                "title": _clean(f"Comment by u/{name} on {post.title}"),
                "link": link,
                "description": _clean(comment.body_html) if show_body else None,
                "unique_id": link,
                "author_name": name,
                "pubdate": _aware(comment.created_at),
                "updateddate": _aware(comment.edited_at or comment.created_at),
            }

        def build():
            rows = list(comments[(page - 1) * PAGE_SIZE : page * PAGE_SIZE + 1])
            return _build_feed(
                request,
                title=f"Comments on {post.title}",
                subtitle="",
                link=post_link,
                feed_url=request.build_absolute_uri(request.path),
                items=[item(c) for c in rows[:PAGE_SIZE]],
                fallback=_aware(post.created_at),
                has_next=len(rows) > PAGE_SIZE,
                page=page,
            )

        return _respond(request, build)

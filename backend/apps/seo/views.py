"""Server-rendered Open Graph pages for link previews.

The SPA can't serve meta tags to crawlers, so nginx routes known bots for
/posts/*, /c/* and /u/* here. Humans landing on these URLs are redirected
back to the SPA via a meta refresh.
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.html import escape
from django.views.decorators.cache import cache_page

from apps.communities.models import Community
from apps.posts.models import Post
from apps.posts.services import effective_nsfw, effective_spoiler, root_available

from .atom import _hides_body, feed_links

User = get_user_model()

SITE_NAME = "Nexus"
CACHE_SECONDS = 300


def _render(
    request, *, path: str, title: str, description: str, image=None, feed_url=None
) -> HttpResponse:
    url = f"{settings.FRONTEND_URL}{path}"
    image_tag = ""
    if image:
        image_url = request.build_absolute_uri(image.url)
        image_tag = f'<meta property="og:image" content="{escape(image_url)}">'
    description = description[:300]
    feed_tag = (
        f'<link rel="alternate" type="application/atom+xml" title="{escape(title)}" '
        f'href="{escape(feed_url)}">'
        if feed_url
        else ""
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{escape(title)}</title>
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:type" content="website">
<meta property="og:title" content="{escape(title)}">
<meta property="og:description" content="{escape(description)}">
<meta property="og:url" content="{escape(url)}">
{image_tag}
<meta name="twitter:card" content="{"summary_large_image" if image else "summary"}">
<meta name="description" content="{escape(description)}">
<link rel="canonical" href="{escape(url)}">
{feed_tag}
<meta http-equiv="refresh" content="0;url={escape(url)}">
</head>
<body><a href="{escape(url)}">{escape(title)}</a></body>
</html>"""
    return HttpResponse(html)


@cache_page(CACHE_SECONDS)
def post_og(request, pk: int):
    post = get_object_or_404(
        Post.objects.select_related("community", "crosspost_parent__community"),
        pk=pk,
        is_approved=True,
        deleted_at__isnull=True,
    )
    if post.crosspost_parent is not None and not root_available(post.crosspost_parent):
        # Same mask as the API: the copy came from a post that is gone or held.
        return _render(
            request,
            path=f"/posts/{post.pk}",
            title="[deleted]",
            description=f"Posted in c/{post.community.slug} on {SITE_NAME}",
        )
    fallback = f"Posted in c/{post.community.slug} on {SITE_NAME}"
    # Same rule as the Atom feed: a body with an inline spoiler is left out entirely.
    description = fallback if _hides_body(post.body_html) else (post.body or fallback)
    if effective_nsfw(post):
        # Crawlers are anonymous, so NSFW previews must not leak title, body or image.
        return _render(
            request,
            path=f"/posts/{post.pk}",
            title=f"NSFW post in c/{post.community.slug}",
            description="This post is marked NSFW.",
        )
    if effective_spoiler(post):
        # The title and body usually are the spoiler, so crawlers get neither, nor the image.
        return _render(
            request,
            path=f"/posts/{post.pk}",
            title=f"Spoiler post in c/{post.community.slug}",
            description="This post is marked as a spoiler.",
        )
    return _render(
        request,
        path=f"/posts/{post.pk}",
        title=post.title,
        description=description,
        image=post.image or None,
        feed_url=feed_links(request)["post"](post.pk),
    )


@cache_page(CACHE_SECONDS)
def community_og(request, slug: str):
    community = get_object_or_404(Community, slug=slug)
    if community.is_nsfw:
        return _render(
            request,
            path=f"/c/{community.slug}",
            title=f"c/{community.slug}",
            description=f"An NSFW community on {SITE_NAME}",
        )
    return _render(
        request,
        path=f"/c/{community.slug}",
        title=f"c/{community.slug} — {community.name}",
        description=community.description or f"The {community.name} community on {SITE_NAME}",
        image=community.avatar if community.avatar else None,
        feed_url=feed_links(request)["community"](community.slug),
    )


@cache_page(CACHE_SECONDS)
def user_og(request, username: str):
    user = get_object_or_404(User, username__iexact=username, is_active=True)
    return _render(
        request,
        path=f"/u/{user.username}",
        title=f"u/{user.username} on {SITE_NAME}",
        description=user.bio or f"{user.username}'s profile on {SITE_NAME}",
        image=user.avatar if user.avatar else None,
        feed_url=feed_links(request)["user"](user.username),
    )

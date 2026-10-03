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

User = get_user_model()

SITE_NAME = "Nexus"
CACHE_SECONDS = 300


def _render(request, *, path: str, title: str, description: str, image=None) -> HttpResponse:
    url = f"{settings.FRONTEND_URL}{path}"
    image_tag = ""
    if image:
        image_url = request.build_absolute_uri(image.url)
        image_tag = f'<meta property="og:image" content="{escape(image_url)}">'
    description = description[:300]
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
<meta http-equiv="refresh" content="0;url={escape(url)}">
</head>
<body><a href="{escape(url)}">{escape(title)}</a></body>
</html>"""
    return HttpResponse(html)


@cache_page(CACHE_SECONDS)
def post_og(request, pk: int):
    post = get_object_or_404(
        Post.objects.select_related("community"), pk=pk, is_approved=True, deleted_at__isnull=True
    )
    description = post.body or f"Posted in c/{post.community.slug} on {SITE_NAME}"
    nsfw = post.is_nsfw or post.community.is_nsfw
    return _render(
        request,
        path=f"/posts/{post.pk}",
        title=post.title,
        description=description,
        image=post.image if post.image and not nsfw else None,
    )


@cache_page(CACHE_SECONDS)
def community_og(request, slug: str):
    community = get_object_or_404(Community, slug=slug)
    return _render(
        request,
        path=f"/c/{community.slug}",
        title=f"c/{community.slug} — {community.name}",
        description=community.description or f"The {community.name} community on {SITE_NAME}",
        image=community.avatar if community.avatar else None,
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
    )

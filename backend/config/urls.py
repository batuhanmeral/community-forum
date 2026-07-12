from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.comments.urls import comments_urlpatterns, post_comments_urlpatterns
from apps.communities.urls import urlpatterns as communities_urlpatterns
from apps.messaging.urls import urlpatterns as messaging_urlpatterns
from apps.posts.urls import (
    community_posts_urlpatterns,
    feed_urlpatterns,
    posts_urlpatterns,
)
from apps.users.urls import auth_urlpatterns, users_urlpatterns
from apps.votes.urls import urlpatterns as votes_urlpatterns

api_v1_patterns = [
    path("auth/", include((auth_urlpatterns, "auth"))),
    path("users/", include((users_urlpatterns, "users"))),
    path("", include((communities_urlpatterns, "communities"))),
    path("", include((community_posts_urlpatterns, "community-posts"))),
    path("", include((posts_urlpatterns, "posts"))),
    path("", include((feed_urlpatterns, "feed"))),
    path("", include((post_comments_urlpatterns, "post-comments"))),
    path("", include((comments_urlpatterns, "comments"))),
    path("", include((votes_urlpatterns, "votes"))),
    path("", include((messaging_urlpatterns, "messaging"))),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include((api_v1_patterns, "api_v1"))),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

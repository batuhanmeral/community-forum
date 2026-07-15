from django.urls import path

from .feed import FeedView, FollowingFeedView
from .views import (
    CommunityPostListCreateView,
    PostDetailView,
    PostRevisionListView,
    PostStickyView,
)

community_posts_urlpatterns = [
    path(
        "communities/<slug:slug>/posts/",
        CommunityPostListCreateView.as_view(),
        name="community-posts",
    ),
]

posts_urlpatterns = [
    path("posts/<int:pk>/", PostDetailView.as_view(), name="post-detail"),
    path("posts/<int:pk>/sticky/", PostStickyView.as_view(), name="post-sticky"),
    path(
        "posts/<int:pk>/revisions/",
        PostRevisionListView.as_view(),
        name="post-revisions",
    ),
]

feed_urlpatterns = [
    path("feed/", FeedView.as_view(), name="feed"),
    path("feed/following/", FollowingFeedView.as_view(), name="feed-following"),
]

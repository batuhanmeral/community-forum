from django.urls import path

from .feed import FeedView, FollowingFeedView
from .views import (
    ApprovalQueueView,
    CommunityPostListCreateView,
    PostApprovalView,
    PostDetailView,
    PostRevisionListView,
    PostStickyView,
    UserPostListView,
)

community_posts_urlpatterns = [
    path(
        "communities/<slug:slug>/posts/",
        CommunityPostListCreateView.as_view(),
        name="community-posts",
    ),
    path(
        "communities/<slug:slug>/mod/approval-queue/",
        ApprovalQueueView.as_view(),
        name="community-approval-queue",
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
    path(
        "posts/<int:pk>/approve/",
        PostApprovalView.as_view(),
        name="post-approve",
    ),
    path(
        "users/<str:username>/posts/",
        UserPostListView.as_view(),
        name="user-posts",
    ),
]

feed_urlpatterns = [
    path("feed/", FeedView.as_view(), name="feed"),
    path("feed/following/", FollowingFeedView.as_view(), name="feed-following"),
]

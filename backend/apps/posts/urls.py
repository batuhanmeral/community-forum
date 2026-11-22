from django.urls import path

from .customfeeds import MyFeedsView, UserFeedDetailView, UserFeedListView, UserFeedPostsView
from .feed import FeedView, FollowingFeedView
from .views import (
    ApprovalQueueView,
    CommunityFeedExclusionView,
    CommunityPostListCreateView,
    FeedExclusionListView,
    HiddenPostListView,
    PostAcceptView,
    PostApprovalView,
    PostBountyView,
    PostCrosspostView,
    PostDetailView,
    PostHideView,
    PostRevisionListView,
    PostSpoilerView,
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
        "communities/<slug:slug>/feed-exclusion/",
        CommunityFeedExclusionView.as_view(),
        name="community-feed-exclusion",
    ),
    path(
        "users/me/feed-exclusions/",
        FeedExclusionListView.as_view(),
        name="users-me-feed-exclusions",
    ),
    path("users/me/feeds/", MyFeedsView.as_view(), name="users-me-feeds"),
    path("users/<str:username>/feeds/", UserFeedListView.as_view(), name="user-feeds"),
    path(
        "users/<str:username>/feeds/<slug:slug>/",
        UserFeedDetailView.as_view(),
        name="user-feed-detail",
    ),
    path(
        "users/<str:username>/feeds/<slug:slug>/posts/",
        UserFeedPostsView.as_view(),
        name="user-feed-posts",
    ),
    path("posts/<int:pk>/hide/", PostHideView.as_view(), name="post-hide"),
    path("users/me/hidden/", HiddenPostListView.as_view(), name="users-me-hidden"),
    path("posts/<int:pk>/crosspost/", PostCrosspostView.as_view(), name="post-crosspost"),
    path("posts/<int:pk>/spoiler/", PostSpoilerView.as_view(), name="post-spoiler"),
    path("posts/<int:pk>/accept/", PostAcceptView.as_view(), name="post-accept"),
    path("posts/<int:pk>/bounty/", PostBountyView.as_view(), name="post-bounty"),
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

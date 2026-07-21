from django.urls import path

from .views import (
    BlockedListView,
    BlockToggleView,
    FollowersListView,
    FollowingListView,
    FollowToggleView,
)

urlpatterns = [
    path(
        "users/me/blocked/",
        BlockedListView.as_view(),
        name="user-blocked-list",
    ),
    path(
        "users/<str:username>/follow/",
        FollowToggleView.as_view(),
        name="user-follow",
    ),
    path(
        "users/<str:username>/block/",
        BlockToggleView.as_view(),
        name="user-block",
    ),
    path(
        "users/<str:username>/followers/",
        FollowersListView.as_view(),
        name="user-followers",
    ),
    path(
        "users/<str:username>/following/",
        FollowingListView.as_view(),
        name="user-following",
    ),
]

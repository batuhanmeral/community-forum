from django.urls import path

from .views import FollowersListView, FollowingListView, FollowToggleView

urlpatterns = [
    path(
        "users/<str:username>/follow/",
        FollowToggleView.as_view(),
        name="user-follow",
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

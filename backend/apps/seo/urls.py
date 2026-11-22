from django.urls import path

from .atom import CommunityAtomView, PostCommentsAtomView, UserAtomView
from .views import community_og, post_og, user_og

urlpatterns = [
    path("posts/<int:pk>/", post_og, name="og-post"),
    path("c/<slug:slug>/", community_og, name="og-community"),
    path("u/<str:username>/", user_og, name="og-user"),
]

# Public Atom feeds, mounted under /api/v1/ by config.urls.
atom_urlpatterns = [
    path("communities/<slug:slug>/feed.atom", CommunityAtomView.as_view(), name="atom-community"),
    path("users/<str:username>/posts.atom", UserAtomView.as_view(), name="atom-user"),
    path("posts/<int:pk>/comments.atom", PostCommentsAtomView.as_view(), name="atom-post-comments"),
]

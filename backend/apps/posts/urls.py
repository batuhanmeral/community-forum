from django.urls import path

from .views import CommunityPostListCreateView, PostDetailView, PostStickyView

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
]

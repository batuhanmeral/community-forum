from django.urls import path

from .trending import TrendingCommunitiesView, TrendingPostsView
from .views import SearchView

urlpatterns = [
    path("search/", SearchView.as_view(), name="search"),
    path(
        "trending/communities/",
        TrendingCommunitiesView.as_view(),
        name="trending-communities",
    ),
    path("trending/posts/", TrendingPostsView.as_view(), name="trending-posts"),
]

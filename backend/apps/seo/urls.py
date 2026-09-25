from django.urls import path

from .views import community_og, post_og, user_og

urlpatterns = [
    path("posts/<int:pk>/", post_og, name="og-post"),
    path("c/<slug:slug>/", community_og, name="og-community"),
    path("u/<str:username>/", user_og, name="og-user"),
]

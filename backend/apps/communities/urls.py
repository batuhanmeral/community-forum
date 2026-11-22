from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    CommunityRuleDetailView,
    CommunityRuleListCreateView,
    CommunityViewSet,
    FlairDetailView,
    FlairListCreateView,
    UserFlairAssignView,
    UserFlairDetailView,
    UserFlairListCreateView,
)

router = DefaultRouter()
router.register(r"communities", CommunityViewSet, basename="community")

urlpatterns = router.urls + [
    path("communities/<slug:slug>/user-flairs/", UserFlairListCreateView.as_view()),
    path("communities/<slug:slug>/user-flairs/<int:pk>/", UserFlairDetailView.as_view()),
    path("communities/<slug:slug>/user-flair/", UserFlairAssignView.as_view()),
    path(
        "communities/<slug:slug>/rules/",
        CommunityRuleListCreateView.as_view(),
        name="community-rules",
    ),
    path(
        "communities/<slug:slug>/rules/<int:pk>/",
        CommunityRuleDetailView.as_view(),
        name="community-rule-detail",
    ),
    path(
        "communities/<slug:slug>/flairs/",
        FlairListCreateView.as_view(),
        name="community-flairs",
    ),
    path(
        "communities/<slug:slug>/flairs/<int:pk>/",
        FlairDetailView.as_view(),
        name="community-flair-detail",
    ),
]

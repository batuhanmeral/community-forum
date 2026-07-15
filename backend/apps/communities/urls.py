from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    CommunityRuleDetailView,
    CommunityRuleListCreateView,
    CommunityViewSet,
)

router = DefaultRouter()
router.register(r"communities", CommunityViewSet, basename="community")

urlpatterns = router.urls + [
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
]

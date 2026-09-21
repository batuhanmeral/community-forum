from django.urls import path

from .views import (
    CommunityBanView,
    CommunityReportListView,
    MembershipRoleView,
    ModLogView,
    ReportCreateView,
    ReportDismissView,
    ReportResolveView,
)

urlpatterns = [
    path("reports/", ReportCreateView.as_view(), name="report-create"),
    path(
        "communities/<slug:slug>/mod/reports/",
        CommunityReportListView.as_view(),
        name="community-mod-reports",
    ),
    path(
        "communities/<slug:slug>/mod/reports/<int:pk>/resolve/",
        ReportResolveView.as_view(),
        name="community-mod-report-resolve",
    ),
    path(
        "communities/<slug:slug>/mod/reports/<int:pk>/dismiss/",
        ReportDismissView.as_view(),
        name="community-mod-report-dismiss",
    ),
    path(
        "communities/<slug:slug>/mod/ban/<str:username>/",
        CommunityBanView.as_view(),
        name="community-mod-ban",
    ),
    path(
        "communities/<slug:slug>/mod/members/<str:username>/",
        MembershipRoleView.as_view(),
        name="community-mod-member",
    ),
    path(
        "communities/<slug:slug>/mod/log/",
        ModLogView.as_view(),
        name="community-mod-log",
    ),
]

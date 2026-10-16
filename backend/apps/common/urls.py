from django.urls import path

from .views import HealthView, MarkdownPreviewView

urlpatterns = [
    path("markdown/preview/", MarkdownPreviewView.as_view(), name="markdown-preview"),
    path("health/", HealthView.as_view(), name="health"),
]

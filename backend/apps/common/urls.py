from django.urls import path

from .views import MarkdownPreviewView

urlpatterns = [
    path("markdown/preview/", MarkdownPreviewView.as_view(), name="markdown-preview"),
]

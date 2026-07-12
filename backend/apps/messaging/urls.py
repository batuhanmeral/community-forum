from django.urls import path

from .views import (
    ConversationListCreateView,
    ConversationReadView,
    MessageListCreateView,
)

urlpatterns = [
    path("conversations/", ConversationListCreateView.as_view(), name="conversation-list"),
    path(
        "conversations/<int:pk>/messages/",
        MessageListCreateView.as_view(),
        name="conversation-messages",
    ),
    path(
        "conversations/<int:pk>/read/",
        ConversationReadView.as_view(),
        name="conversation-read",
    ),
]

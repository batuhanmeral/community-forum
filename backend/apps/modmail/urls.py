from django.urls import path

from .views import (
    CommunityModmailView,
    ModmailMessagesView,
    ModmailReadView,
    ModmailThreadView,
    MyModmailView,
)

urlpatterns = [
    path("communities/<slug:slug>/modmail/", CommunityModmailView.as_view(), name="modmail-inbox"),
    path("modmail/mine/", MyModmailView.as_view(), name="modmail-mine"),
    path("modmail/<int:pk>/", ModmailThreadView.as_view(), name="modmail-thread"),
    path("modmail/<int:pk>/messages/", ModmailMessagesView.as_view(), name="modmail-messages"),
    path("modmail/<int:pk>/read/", ModmailReadView.as_view(), name="modmail-read"),
]

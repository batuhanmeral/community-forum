from django.urls import path

from .views import PollDetailView, PollVoteView

urlpatterns = [
    path("polls/<int:pk>/", PollDetailView.as_view(), name="poll-detail"),
    path("polls/<int:pk>/vote/", PollVoteView.as_view(), name="poll-vote"),
]

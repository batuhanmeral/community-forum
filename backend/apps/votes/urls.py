from django.urls import path

from .views import VoteView

urlpatterns = [
    path("vote/", VoteView.as_view(), name="vote"),
]

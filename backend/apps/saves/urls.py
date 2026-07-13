from django.urls import path

from .views import SavedItemListCreateView

urlpatterns = [
    path("saved/", SavedItemListCreateView.as_view(), name="saved-list"),
]

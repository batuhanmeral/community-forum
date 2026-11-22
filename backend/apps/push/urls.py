from django.urls import path

from .views import PreferencesView, PushConfigView, SubscriptionView

urlpatterns = [
    path("push/config/", PushConfigView.as_view(), name="push-config"),
    path("push/subscriptions/", SubscriptionView.as_view(), name="push-subscriptions"),
    path("push/preferences/", PreferencesView.as_view(), name="push-preferences"),
]

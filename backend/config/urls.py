from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.communities.urls import urlpatterns as communities_urlpatterns
from apps.users.urls import auth_urlpatterns, users_urlpatterns

api_v1_patterns = [
    path("auth/", include((auth_urlpatterns, "auth"))),
    path("users/", include((users_urlpatterns, "users"))),
    path("", include((communities_urlpatterns, "communities"))),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include((api_v1_patterns, "api_v1"))),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

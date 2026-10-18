from django.contrib.auth import get_user_model
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import Count, Q
from rest_framework import permissions
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView

from apps.communities.models import Community
from apps.communities.serializers import CommunitySerializer
from apps.posts.feed import _apply_nsfw_filter
from apps.posts.models import Post
from apps.posts.serializers import PostSerializer
from apps.posts.views import _annotate_score, _base_post_qs
from apps.users.serializers import PublicUserSerializer

User = get_user_model()

_TYPE_CONFIG = {
    "post": (Post, PostSerializer),
    "community": (Community, CommunitySerializer),
    "user": (User, PublicUserSerializer),
}


class SearchView(ListAPIView):
    permission_classes = (permissions.AllowAny,)

    def _config(self):
        type_param = self.request.query_params.get("type", "post").lower()
        if type_param not in _TYPE_CONFIG:
            raise ValidationError({"type": f"must be one of {sorted(_TYPE_CONFIG)}."})
        return type_param, _TYPE_CONFIG[type_param]

    def get_serializer_class(self):
        _, (_, serializer_cls) = self._config()
        return serializer_cls

    def get_queryset(self):
        query = self.request.query_params.get("q", "").strip()
        if not query:
            raise ValidationError({"q": "Search query 'q' is required."})
        type_param, (model, _) = self._config()
        sq = SearchQuery(query, search_type="websearch")
        qs = model.objects.filter(search_vector=sq)
        if type_param == "post":
            qs = qs.filter(is_approved=True, deleted_at__isnull=True)
            qs = _apply_nsfw_filter(qs, self.request)
            qs = _annotate_score(_base_post_qs(qs, user=self.request.user))
        elif type_param == "community":
            qs = qs.annotate(
                member_count=Count("memberships", filter=Q(memberships__is_banned=False))
            )
        elif type_param == "user":
            qs = qs.filter(is_active=True)
        return qs.annotate(rank=SearchRank("search_vector", sq)).order_by("-rank")

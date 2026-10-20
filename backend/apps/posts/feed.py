from django.db.models import Q
from rest_framework import generics, permissions

from apps.communities.services import joined_community_ids

from .models import Post
from .serializers import PostSerializer
from .views import _annotate_score, _apply_sort, _apply_time_window, _base_post_qs


def _apply_nsfw_filter(qs, request):
    """Hide NSFW unless an authed user opts in via ?nsfw=show or their profile pref."""
    if request.user.is_authenticated:
        param = request.query_params.get("nsfw")
        if param == "show" or (param is None and request.user.show_nsfw):
            return qs
    return qs.exclude(Q(is_nsfw=True) | Q(community__is_nsfw=True))


class FeedView(generics.ListAPIView):
    """Personalized feed for joined communities; falls back to popular for anon."""

    serializer_class = PostSerializer
    permission_classes = (permissions.AllowAny,)

    def get_queryset(self):
        request = self.request
        scope = request.query_params.get("scope")
        if request.user.is_authenticated and scope != "all":
            qs = Post.objects.filter(community_id__in=joined_community_ids(request.user))
        else:
            qs = Post.objects.all()
        qs = qs.filter(is_approved=True, deleted_at__isnull=True)
        qs = _annotate_score(_base_post_qs(qs, user=request.user))
        qs = _apply_nsfw_filter(qs, request)
        sort = request.query_params.get("sort", "new" if request.user.is_authenticated else "top")
        if sort == "top":
            qs = _apply_time_window(qs, request.query_params.get("t"))
        return _apply_sort(qs, sort)


class FollowingFeedView(generics.ListAPIView):
    """Posts authored by users the requester follows."""

    serializer_class = PostSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        request = self.request
        qs = Post.objects.filter(
            author__followers__follower=request.user,
            is_approved=True,
            deleted_at__isnull=True,
        ).distinct()
        qs = _annotate_score(_base_post_qs(qs, user=request.user))
        qs = _apply_nsfw_filter(qs, request)
        sort = request.query_params.get("sort", "new")
        if sort == "top":
            qs = _apply_time_window(qs, request.query_params.get("t"))
        return _apply_sort(qs, sort)

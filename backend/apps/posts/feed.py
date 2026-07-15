from rest_framework import generics, permissions

from .models import Post
from .serializers import PostSerializer
from .views import _annotate_score, _apply_sort, _apply_time_window


def _apply_nsfw_filter(qs, request):
    if request.query_params.get("nsfw") == "show" and request.user.is_authenticated:
        return qs
    return qs.exclude(is_nsfw=True)


class FeedView(generics.ListAPIView):
    """Personalized feed for joined communities; falls back to popular for anon."""

    serializer_class = PostSerializer
    permission_classes = (permissions.AllowAny,)

    def get_queryset(self):
        request = self.request
        if request.user.is_authenticated:
            qs = Post.objects.filter(community__memberships__user=request.user).distinct()
        else:
            qs = Post.objects.all()
        qs = _annotate_score(qs)
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
        qs = Post.objects.filter(author__followers__follower=request.user).distinct()
        qs = _annotate_score(qs)
        qs = _apply_nsfw_filter(qs, request)
        sort = request.query_params.get("sort", "new")
        if sort == "top":
            qs = _apply_time_window(qs, request.query_params.get("t"))
        return _apply_sort(qs, sort)

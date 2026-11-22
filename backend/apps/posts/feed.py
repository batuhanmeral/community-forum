from rest_framework import generics, permissions

from apps.communities.services import joined_community_ids

from .models import Post
from .serializers import PostSerializer
from .services import nsfw_q
from .views import (
    _annotate_score,
    _apply_answered_filter,
    _apply_sort,
    _apply_time_window,
    _base_post_qs,
    _exclude_feed_communities,
    _exclude_hidden,
)


def nsfw_allowed(request) -> bool:
    """True when an authed user opts in via ?nsfw=show or their profile pref."""
    if not request.user.is_authenticated:
        return False
    param = request.query_params.get("nsfw")
    return param == "show" or (param is None and request.user.show_nsfw)


def _apply_nsfw_filter(qs, request):
    if nsfw_allowed(request):
        return qs
    return qs.exclude(nsfw_q())


def build_post_feed(request, qs, default_sort: str):
    """The shared feed pipeline: visibility, score, NSFW, hidden, time window, filters and sort.

    Every list of posts (Home, Following, custom feeds, ...) goes through this so the
    rules cannot drift apart.
    """
    qs = qs.filter(is_approved=True, deleted_at__isnull=True)
    qs = _annotate_score(_base_post_qs(qs, user=request.user))
    qs = _exclude_hidden(_apply_nsfw_filter(qs, request), request.user)
    sort = request.query_params.get("sort", default_sort)
    qs = _apply_time_window(qs, request.query_params.get("t"))
    return _apply_sort(_apply_answered_filter(qs, request), sort)


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
            # Popular/All only: Home (joined communities) is deliberately left alone.
            qs = _exclude_feed_communities(qs, request.user)
        return build_post_feed(request, qs, "new" if request.user.is_authenticated else "top")


class FollowingFeedView(generics.ListAPIView):
    """Posts authored by users the requester follows."""

    serializer_class = PostSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        request = self.request
        qs = Post.objects.filter(author__followers__follower=request.user).distinct()
        return build_post_feed(request, qs, "new")

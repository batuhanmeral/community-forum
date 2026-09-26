from datetime import timedelta

from django.db.models import Count, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from rest_framework import permissions
from rest_framework.generics import ListAPIView

from apps.communities.models import Community
from apps.communities.serializers import CommunitySerializer
from apps.posts.models import Post
from apps.posts.serializers import PostSerializer

WINDOW_HOURS = 24
CACHE_SECONDS = 300


def _since():
    return timezone.now() - timedelta(hours=WINDOW_HOURS)


@method_decorator(cache_page(CACHE_SECONDS), name="dispatch")
@method_decorator(vary_on_headers("Authorization"), name="dispatch")
class TrendingCommunitiesView(ListAPIView):
    serializer_class = CommunitySerializer
    permission_classes = (permissions.AllowAny,)

    def get_queryset(self):
        from apps.comments.models import Comment
        from apps.posts.models import Post as PostModel

        since = _since()
        recent_posts = (
            PostModel.objects.filter(community=OuterRef("pk"), created_at__gte=since)
            .order_by()
            .values("community")
            .annotate(c=Count("*"))
            .values("c")
        )
        recent_comments = (
            Comment.objects.filter(post__community=OuterRef("pk"), created_at__gte=since)
            .order_by()
            .values("post__community")
            .annotate(c=Count("*"))
            .values("c")
        )
        return Community.objects.annotate(
            member_count=Count("memberships", distinct=True),
            recent_posts=Coalesce(Subquery(recent_posts), 0),
            recent_comments=Coalesce(Subquery(recent_comments), 0),
        ).order_by("-recent_posts", "-recent_comments", "-id")[:20]


@method_decorator(cache_page(CACHE_SECONDS), name="dispatch")
@method_decorator(vary_on_headers("Authorization"), name="dispatch")
class TrendingPostsView(ListAPIView):
    serializer_class = PostSerializer
    permission_classes = (permissions.AllowAny,)

    def get_queryset(self):
        from apps.posts.views import _annotate_score, _base_post_qs

        since = _since()
        return _annotate_score(
            _base_post_qs(
                Post.objects.filter(
                    created_at__gte=since,
                    is_nsfw=False,
                    is_approved=True,
                    deleted_at__isnull=True,
                )
            )
        ).order_by("-score", "-created_at")[:20]

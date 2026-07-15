from datetime import timedelta

from django.db.models import ExpressionWrapper, FloatField, Sum
from django.db.models.expressions import RawSQL
from django.db.models.functions import Coalesce, Extract
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.communities.models import Community
from apps.notifications.services import notify

from .models import Post, PostRevision
from .permissions import (
    IsAuthorOrModeratorForDelete,
    IsCommunityMember,
    is_moderator,
)
from .serializers import PostRevisionSerializer, PostSerializer

MAX_STICKY_PER_COMMUNITY = 2


TIME_WINDOWS = {
    "hour": timedelta(hours=1),
    "day": timedelta(days=1),
    "week": timedelta(weeks=1),
    "month": timedelta(days=30),
    "year": timedelta(days=365),
}


def _annotate_score(qs):
    return qs.annotate(score=Coalesce(Sum("votes__value"), 0))


def _apply_time_window(qs, t: str | None):
    if not t or t == "all":
        return qs
    delta = TIME_WINDOWS.get(t)
    if delta is None:
        return qs
    from django.utils import timezone

    return qs.filter(created_at__gte=timezone.now() - delta)


def _annotate_hot(qs):
    """Reddit's hot: sign(score) * log10(max(|score|,1)) + epoch/45000.

    Postgres can compute this in SQL via GREATEST/LOG/SIGN.
    """
    return qs.annotate(
        hot=ExpressionWrapper(
            RawSQL(
                "SIGN(COALESCE((SELECT SUM(value) FROM votes_vote v "
                "WHERE v.content_type_id = ("
                "  SELECT id FROM django_content_type WHERE app_label='posts' AND model='post'"
                ") AND v.object_id = posts_post.id), 0)) "
                "* LOG(10, GREATEST(ABS(COALESCE((SELECT SUM(value) FROM votes_vote v "
                "WHERE v.content_type_id = ("
                "  SELECT id FROM django_content_type WHERE app_label='posts' AND model='post'"
                ") AND v.object_id = posts_post.id), 0)), 1)) "
                "+ EXTRACT(EPOCH FROM posts_post.created_at) / 45000.0",
                [],
            ),
            output_field=FloatField(),
        )
    )


def _apply_sort(qs, sort: str):
    if sort == "top":
        return qs.order_by("-is_pinned", "-score", "-created_at")
    if sort == "hot":
        return _annotate_hot(qs).order_by("-is_pinned", "-hot")
    return qs.order_by("-is_pinned", "-created_at")


class CommunityPostListCreateView(generics.ListCreateAPIView):
    serializer_class = PostSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly, IsCommunityMember)
    parser_classes = (JSONParser, FormParser, MultiPartParser)
    throttle_scope = "write"

    def get_community(self) -> Community:
        if not hasattr(self, "_community"):
            self._community = get_object_or_404(Community, slug=self.kwargs["slug"])
        return self._community

    def get_queryset(self):
        qs = _annotate_score(Post.objects.filter(community=self.get_community()))
        sort = self.request.query_params.get("sort", "new")
        if sort == "top":
            qs = _apply_time_window(qs, self.request.query_params.get("t"))
        return _apply_sort(qs, sort)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["community"] = self.get_community()
        return ctx

    def perform_create(self, serializer):
        post = serializer.save(author=self.request.user, community=self.get_community())
        from apps.comments.views import notify_mentions

        notify_mentions(post.body, actor=self.request.user, target=post)


class PostDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PostSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly, IsAuthorOrModeratorForDelete)
    parser_classes = (JSONParser, FormParser, MultiPartParser)
    queryset = _annotate_score(Post.objects.all())

    def perform_destroy(self, instance):
        if instance.deleted_at is not None:
            return
        instance.deleted_at = timezone.now()
        instance.deleted_by = self.request.user
        instance.save(update_fields=["deleted_at", "deleted_by"])
        if instance.author_id != self.request.user.id:
            notify(instance.author, actor=self.request.user, verb="mod_action", target=instance)

    def perform_update(self, serializer):
        instance = self.get_object()
        old_title, old_body = instance.title, instance.body
        post = serializer.save()
        if (post.title, post.body) != (old_title, old_body):
            PostRevision.objects.create(
                post=post, title=old_title, body=old_body, edited_by=self.request.user
            )
            post.edited_at = timezone.now()
            post.save(update_fields=["edited_at"])


class PostRevisionListView(generics.ListAPIView):
    serializer_class = PostRevisionSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        post = get_object_or_404(Post, pk=self.kwargs["pk"])
        if post.author_id != self.request.user.id and not is_moderator(self.request.user, post.community):
            raise PermissionDenied("Only the author or a moderator can view edit history.")
        return post.revisions.select_related("edited_by")


class PostStickyView(APIView):
    """Mod-only sticky toggle (POST=pin, DELETE=unpin)."""

    permission_classes = (permissions.IsAuthenticated,)

    def _get_post(self, pk):
        return get_object_or_404(Post, pk=pk)

    def _require_mod(self, request, post):
        if not is_moderator(request.user, post.community):
            raise PermissionDenied("Moderator role required.")

    def post(self, request, pk):
        post = self._get_post(pk)
        self._require_mod(request, post)
        if post.is_pinned:
            return Response({"is_pinned": True}, status=status.HTTP_200_OK)
        pinned_count = Post.objects.filter(
            community=post.community, is_pinned=True
        ).count()
        if pinned_count >= MAX_STICKY_PER_COMMUNITY:
            raise ValidationError(
                f"Sticky limit reached ({MAX_STICKY_PER_COMMUNITY} per community)."
            )
        post.is_pinned = True
        post.save(update_fields=["is_pinned"])
        notify(post.author, actor=request.user, verb="mod_action", target=post)
        return Response({"is_pinned": True}, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        post = self._get_post(pk)
        self._require_mod(request, post)
        if post.is_pinned:
            post.is_pinned = False
            post.save(update_fields=["is_pinned"])
            notify(post.author, actor=request.user, verb="mod_action", target=post)
        return Response({"is_pinned": False}, status=status.HTTP_200_OK)

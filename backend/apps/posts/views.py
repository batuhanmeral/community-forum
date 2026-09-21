from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import (
    Count,
    ExpressionWrapper,
    FloatField,
    IntegerField,
    OuterRef,
    Subquery,
    Sum,
)
from django.db.models.expressions import RawSQL
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.communities.models import Community
from apps.moderation.models import ModAction
from apps.moderation.services import log_mod_action
from apps.notifications.services import notify

from .models import Post, PostRevision
from .permissions import (
    IsAuthorOrModeratorForDelete,
    IsCommunityMember,
    is_moderator,
)
from .serializers import PostRevisionSerializer, PostSerializer

User = get_user_model()

MAX_STICKY_PER_COMMUNITY = 2


TIME_WINDOWS = {
    "hour": timedelta(hours=1),
    "day": timedelta(days=1),
    "week": timedelta(weeks=1),
    "month": timedelta(days=30),
    "year": timedelta(days=365),
}


def _annotate_score(qs):
    from apps.comments.models import Comment

    # comment_count as a subquery: a join here would inflate Sum("votes__value").
    comment_count_sq = (
        Comment.objects.filter(post=OuterRef("pk"))
        .order_by()
        .values("post")
        .annotate(c=Count("pk"))
        .values("c")
    )
    return qs.annotate(
        score=Coalesce(Sum("votes__value"), 0),
        comment_count=Coalesce(Subquery(comment_count_sq, output_field=IntegerField()), 0),
    )


def _base_post_qs(qs=None):
    """Common relations every PostSerializer render needs (avoids N+1)."""
    if qs is None:
        qs = Post.objects.all()
    return qs.select_related("author", "community", "flair", "poll").prefetch_related(
        "votes", "saves", "poll__options"
    )


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
        qs = _annotate_score(
            _base_post_qs(
                Post.objects.filter(
                    community=self.get_community(),
                    is_approved=True,
                    deleted_at__isnull=True,
                )
            )
        )
        sort = self.request.query_params.get("sort", "new")
        if sort == "top":
            qs = _apply_time_window(qs, self.request.query_params.get("t"))
        return _apply_sort(qs, sort)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["community"] = self.get_community()
        return ctx

    def perform_create(self, serializer):
        community = self.get_community()
        author_is_mod = is_moderator(self.request.user, community)
        # If community requires approval, hide post until a mod approves.
        is_approved = not community.requires_approval or author_is_mod
        # AutoMod: hold posts matching a banned keyword (mods bypass).
        matched_kw = None
        if is_approved and not author_is_mod:
            matched_kw = community.matches_banned_keyword(
                serializer.validated_data.get("title", ""),
                serializer.validated_data.get("body", ""),
            )
            if matched_kw:
                is_approved = False
        post = serializer.save(
            author=self.request.user,
            community=community,
            is_approved=is_approved,
        )
        if matched_kw:
            log_mod_action(
                community,
                action=ModAction.Action.AUTOMOD_HOLD,
                target=post,
                detail=f"matched keyword: {matched_kw}",
            )
        from apps.comments.views import notify_mentions

        notify_mentions(post.body, actor=self.request.user, target=post)


class UserPostListView(generics.ListAPIView):
    """Public list of a user's (non-deleted, approved) posts, newest first."""

    serializer_class = PostSerializer
    permission_classes = (permissions.AllowAny,)

    def get_queryset(self):
        author = get_object_or_404(User, username__iexact=self.kwargs["username"])
        qs = _annotate_score(
            _base_post_qs(
                Post.objects.filter(author=author, is_approved=True, deleted_at__isnull=True)
            )
        )
        return _apply_sort(qs, self.request.query_params.get("sort", "new"))


class PostDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PostSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly, IsAuthorOrModeratorForDelete)
    parser_classes = (JSONParser, FormParser, MultiPartParser)
    queryset = _annotate_score(_base_post_qs())

    def perform_destroy(self, instance):
        if instance.deleted_at is not None:
            return
        instance.deleted_at = timezone.now()
        instance.deleted_by = self.request.user
        instance.save(update_fields=["deleted_at", "deleted_by"])
        if instance.author_id != self.request.user.id:
            log_mod_action(
                instance.community,
                actor=self.request.user,
                action=ModAction.Action.POST_REMOVE,
                target=instance,
            )
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
        if post.author_id != self.request.user.id and not is_moderator(
            self.request.user, post.community
        ):
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
        pinned_count = Post.objects.filter(community=post.community, is_pinned=True).count()
        if pinned_count >= MAX_STICKY_PER_COMMUNITY:
            raise ValidationError(
                f"Sticky limit reached ({MAX_STICKY_PER_COMMUNITY} per community)."
            )
        post.is_pinned = True
        post.save(update_fields=["is_pinned"])
        log_mod_action(
            post.community, actor=request.user, action=ModAction.Action.POST_PIN, target=post
        )
        notify(post.author, actor=request.user, verb="mod_action", target=post)
        return Response({"is_pinned": True}, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        post = self._get_post(pk)
        self._require_mod(request, post)
        if post.is_pinned:
            post.is_pinned = False
            post.save(update_fields=["is_pinned"])
            log_mod_action(
                post.community, actor=request.user, action=ModAction.Action.POST_UNPIN, target=post
            )
            notify(post.author, actor=request.user, verb="mod_action", target=post)
        return Response({"is_pinned": False}, status=status.HTTP_200_OK)


class ApprovalQueueView(generics.ListAPIView):
    """Mod-only list of pending posts awaiting approval."""

    serializer_class = PostSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_community(self) -> Community:
        if not hasattr(self, "_community"):
            self._community = get_object_or_404(Community, slug=self.kwargs["slug"])
        return self._community

    def get_queryset(self):
        community = self.get_community()
        if not is_moderator(self.request.user, community):
            raise PermissionDenied("Moderator role required.")
        return _annotate_score(
            _base_post_qs(Post.objects.filter(community=community, is_approved=False))
        ).order_by("created_at")


class PostApprovalView(APIView):
    """Mod approve (POST) / reject-delete (DELETE)."""

    permission_classes = (permissions.IsAuthenticated,)

    def _get(self, pk):
        return get_object_or_404(Post, pk=pk)

    def _require_mod(self, request, post):
        if not is_moderator(request.user, post.community):
            raise PermissionDenied("Moderator role required.")

    def post(self, request, pk):
        post = self._get(pk)
        self._require_mod(request, post)
        if not post.is_approved:
            post.is_approved = True
            post.save(update_fields=["is_approved"])
            log_mod_action(
                post.community,
                actor=request.user,
                action=ModAction.Action.POST_APPROVE,
                target=post,
            )
            notify(post.author, actor=request.user, verb="mod_action", target=post)
        return Response({"is_approved": True})

    def delete(self, request, pk):
        post = self._get(pk)
        self._require_mod(request, post)
        if post.deleted_at is None:
            post.deleted_at = timezone.now()
            post.deleted_by = request.user
            post.save(update_fields=["deleted_at", "deleted_by"])
            log_mod_action(
                post.community,
                actor=request.user,
                action=ModAction.Action.POST_REJECT,
                target=post,
            )
            notify(post.author, actor=request.user, verb="mod_action", target=post)
        return Response({"is_approved": False, "deleted": True})

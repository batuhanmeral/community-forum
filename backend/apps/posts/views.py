from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import (
    Count,
    F,
    FloatField,
    IntegerField,
    OuterRef,
    Subquery,
    Sum,
)
from django.db.models.functions import Abs, Cast, Coalesce, Extract, Greatest, Log, Sign
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.throttling import WriteThrottleMixin
from apps.common.viewer import viewer_prefetches
from apps.communities.models import Community
from apps.communities.services import is_banned, is_moderator
from apps.moderation.models import ModAction
from apps.moderation.services import log_mod_action
from apps.notifications.services import notify
from apps.polls.services import poll_prefetches

from .models import Post, PostRevision
from .permissions import IsAuthorOrModeratorForDelete, IsCommunityMember
from .serializers import PostRevisionSerializer, PostSerializer
from .services import can_see_unapproved

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


def _base_post_qs(qs=None, user=None):
    """Common relations every PostSerializer render needs (avoids N+1)."""
    if qs is None:
        qs = Post.objects.all()
    return qs.select_related("author", "community", "flair", "poll").prefetch_related(
        *viewer_prefetches(user), *poll_prefetches(user, "poll__")
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

    Needs the `score` annotation (never NULL: Coalesce'd in _annotate_score).
    """
    score = F("score")
    # Cast: Postgres LOG(10, int) and EXTRACT return numeric; the API wants a float.
    hot = Sign(score) * Log(10, Greatest(Abs(score), 1)) + Extract("created_at", "epoch") / 45000
    return qs.annotate(hot=Cast(hot, FloatField()))


def _apply_sort(qs, sort: str):
    if sort == "top":
        return qs.order_by("-is_pinned", "-score", "-created_at")
    if sort == "hot":
        return _annotate_hot(qs).order_by("-is_pinned", "-hot")
    return qs.order_by("-is_pinned", "-created_at")


def _visible_post(user, pk) -> Post:
    """404 for a held post the user may not see, so mod endpoints can't confirm it exists."""
    post = get_object_or_404(Post, pk=pk)
    if not post.is_approved and not can_see_unapproved(user, post):
        # Same 404 body a missing row gets, so the response can't confirm existence.
        get_object_or_404(Post.objects.none(), pk=pk)
    return post


# Content fields whose change sends an approved post back to the queue.
REAPPROVAL_FIELDS = ("title", "body", "url")


def _edit_hold_reason(post: Post, validated_data: dict) -> str | None:
    # Banned moderators are not moderators (active_membership), but banned users can't edit anyway.
    if not post.is_approved or is_moderator(post.author, post.community):
        return None
    # Only newly added keywords count: a post a mod approved with a keyword must survive typo fixes.
    keyword = post.community.banned_keyword_added(
        (post.title, post.body),
        (validated_data.get("title", post.title), validated_data.get("body", post.body)),
    )
    if keyword:
        return f"matched keyword on edit: {keyword}"
    if not post.community.requires_approval:
        return None
    changed = any(
        field in validated_data and validated_data[field] != getattr(post, field)
        for field in REAPPROVAL_FIELDS
    )
    # An upload, or clearing an existing image, is a change; an absent key is not.
    image_changed = "image" in validated_data and bool(validated_data["image"] or post.image)
    if changed or image_changed:
        return "edited after approval"
    return None


class CommunityPostListCreateView(WriteThrottleMixin, generics.ListCreateAPIView):
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
                ),
                user=self.request.user,
            )
        )
        sort = self.request.query_params.get("sort", "new")
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
            # Everything posted in an NSFW community is NSFW, whatever the author ticked.
            is_nsfw=serializer.validated_data.get("is_nsfw", False) or community.is_nsfw,
        )
        if matched_kw:
            log_mod_action(
                community,
                action=ModAction.Action.AUTOMOD_HOLD,
                target=post,
                detail=f"matched keyword: {matched_kw}",
            )
        # Held posts notify on approval instead, so mentions don't leak early.
        if post.is_approved:
            from apps.comments.views import notify_mentions

            notify_mentions(post.body, actor=self.request.user, target=post)


class UserPostListView(generics.ListAPIView):
    """Public list of a user's (non-deleted, approved) posts, newest first."""

    serializer_class = PostSerializer
    permission_classes = (permissions.AllowAny,)

    def get_queryset(self):
        # feed.py imports this module, so import it lazily.
        from .feed import _apply_nsfw_filter

        author = get_object_or_404(User, username__iexact=self.kwargs["username"])
        qs = _annotate_score(
            _base_post_qs(
                Post.objects.filter(author=author, is_approved=True, deleted_at__isnull=True),
                user=self.request.user,
            )
        )
        if self.request.user != author:
            qs = _apply_nsfw_filter(qs, self.request)
        return _apply_sort(qs, self.request.query_params.get("sort", "new"))


class PostDetailView(WriteThrottleMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PostSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly, IsAuthorOrModeratorForDelete)
    parser_classes = (JSONParser, FormParser, MultiPartParser)
    throttle_scope = "write"

    def get_queryset(self):
        return _annotate_score(_base_post_qs(user=self.request.user))

    def get_object(self):
        post = get_object_or_404(self.filter_queryset(self.get_queryset()), pk=self.kwargs["pk"])
        if not post.is_approved and not can_see_unapproved(self.request.user, post):
            # Same 404 body a missing row gets, so the response can't confirm existence.
            get_object_or_404(Post.objects.none(), pk=self.kwargs["pk"])
        # Permissions only after the visibility check, or a 403 would confirm a hidden post exists.
        self.check_object_permissions(self.request, post)
        return post

    def perform_destroy(self, instance):
        if instance.deleted_at is not None:
            return
        instance.deleted_at = timezone.now()
        instance.deleted_by = self.request.user
        instance.is_pinned = False
        instance.save(update_fields=["deleted_at", "deleted_by", "is_pinned"])
        if instance.author_id != self.request.user.id:
            log_mod_action(
                instance.community,
                actor=self.request.user,
                action=ModAction.Action.POST_REMOVE,
                target=instance,
            )
            notify(instance.author, actor=self.request.user, verb="mod_action", target=instance)

    def perform_update(self, serializer):
        with transaction.atomic():
            self._locked_update(serializer)

    def _locked_update(self, serializer):
        instance = serializer.instance
        # Adopt the locked row (moderation and content) so the save and checks can't use a stale read.
        fresh = (
            Post.objects.select_for_update()
            .filter(pk=instance.pk)
            .values(
                "deleted_at",
                "deleted_by_id",
                "is_approved",
                "is_pinned",
                "title",
                "body",
                "url",
                "image",
                "flair_id",
            )
            .get()
        )
        for field, value in fresh.items():
            setattr(instance, field, value)
        if is_banned(self.request.user, instance.community):
            raise PermissionDenied("You are banned from this community.")
        if instance.deleted_at is not None:
            raise ValidationError("Deleted posts cannot be edited.")
        old_title, old_body = instance.title, instance.body
        reason = _edit_hold_reason(instance, serializer.validated_data)
        # One write carries the hold, so no reader or racing edit ever sees the held edit approved.
        hold = {"is_approved": False, "is_pinned": False} if reason else {}
        post = serializer.save(
            # An NSFW community's posts can't be un-flagged by their author.
            is_nsfw=serializer.validated_data.get("is_nsfw", instance.is_nsfw)
            or instance.community.is_nsfw,
            **hold,
        )
        if (post.title, post.body) != (old_title, old_body):
            PostRevision.objects.create(
                post=post, title=old_title, body=old_body, edited_by=self.request.user
            )
            post.edited_at = timezone.now()
            post.save(update_fields=["edited_at"])
            if post.is_approved:
                from apps.comments.views import notify_mentions

                notify_mentions(post.body, actor=self.request.user, target=post)
        if reason:
            log_mod_action(
                post.community,
                action=ModAction.Action.AUTOMOD_HOLD,
                target=post,
                detail=reason,
            )


class PostRevisionListView(generics.ListAPIView):
    serializer_class = PostRevisionSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        post = _visible_post(self.request.user, self.kwargs["pk"])
        if post.deleted_at is not None:
            # Deleted content is masked everywhere; its earlier versions must not stay readable.
            get_object_or_404(Post.objects.none(), pk=self.kwargs["pk"])
        if post.author_id != self.request.user.id and not is_moderator(
            self.request.user, post.community
        ):
            raise PermissionDenied("Only the author or a moderator can view edit history.")
        return post.revisions.select_related("edited_by")


class PostStickyView(APIView):
    """Mod-only sticky toggle (POST=pin, DELETE=unpin)."""

    permission_classes = (permissions.IsAuthenticated,)

    def _get_post(self, pk):
        return _visible_post(self.request.user, pk)

    def _require_mod(self, request, post):
        if not is_moderator(request.user, post.community):
            raise PermissionDenied("Moderator role required.")

    def post(self, request, pk):
        post = self._get_post(pk)
        self._require_mod(request, post)
        if post.deleted_at is not None or not post.is_approved:
            raise ValidationError("Only visible posts can be pinned.")
        if post.is_pinned:
            return Response({"is_pinned": True}, status=status.HTTP_200_OK)
        pinned_count = Post.objects.filter(
            community=post.community, is_pinned=True, is_approved=True, deleted_at__isnull=True
        ).count()
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
            _base_post_qs(
                Post.objects.filter(
                    community=community, is_approved=False, deleted_at__isnull=True
                ),
                user=self.request.user,
            )
        ).order_by("created_at")


class PostApprovalView(APIView):
    """Mod approve (POST) / reject-delete (DELETE)."""

    permission_classes = (permissions.IsAuthenticated,)

    def _get(self, pk):
        return _visible_post(self.request.user, pk)

    def _require_mod(self, request, post):
        if not is_moderator(request.user, post.community):
            raise PermissionDenied("Moderator role required.")

    def post(self, request, pk):
        post = self._get(pk)
        self._require_mod(request, post)
        # Conditional UPDATE: of two racing approvals only one changes the row and reports it.
        approved = Post.objects.filter(
            pk=post.pk, is_approved=False, deleted_at__isnull=True
        ).update(is_approved=True)
        if approved:
            log_mod_action(
                post.community,
                actor=request.user,
                action=ModAction.Action.POST_APPROVE,
                target=post,
            )
            notify(post.author, actor=request.user, verb="mod_action", target=post)
            from apps.comments.views import notify_mentions

            # Author wrote the mention, so they are the actor, not the approver.
            notify_mentions(post.body, actor=post.author, target=post)
            return Response({"is_approved": True})
        # Lost the race: report what the row really is now.
        state = Post.objects.filter(pk=post.pk).values("is_approved", "deleted_at").first()
        if state is None:
            # Hard-deleted meanwhile: answer exactly as for an id that never existed.
            get_object_or_404(Post.objects.none(), pk=pk)
        return Response(
            {"is_approved": state["is_approved"], "deleted": state["deleted_at"] is not None}
        )

    def delete(self, request, pk):
        post = self._get(pk)
        self._require_mod(request, post)
        rejected = Post.objects.filter(pk=post.pk, deleted_at__isnull=True).update(
            deleted_at=timezone.now(), deleted_by=request.user, is_pinned=False
        )
        if rejected:
            log_mod_action(
                post.community,
                actor=request.user,
                action=ModAction.Action.POST_REJECT,
                target=post,
            )
            notify(post.author, actor=request.user, verb="mod_action", target=post)
        return Response({"is_approved": False, "deleted": True})

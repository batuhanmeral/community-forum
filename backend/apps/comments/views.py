from django.contrib.auth import get_user_model
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import Abs, Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination

from apps.common.throttling import WriteThrottleMixin
from apps.communities.services import is_banned, is_moderator
from apps.notifications.services import notify
from apps.posts.models import Post
from apps.posts.permissions import IsAuthorOrModeratorForDelete
from apps.posts.services import can_see_unapproved

from .lib.mentions import resolve_mentions
from .models import Comment, CommentRevision
from .serializers import CommentRevisionSerializer, CommentSerializer

User = get_user_model()

MAX_COMMENTS_PER_PAGE = 500


class CommentThreadPagination(PageNumberPagination):
    # The client builds the reply tree, so a thread has to arrive in one piece.
    page_size = MAX_COMMENTS_PER_PAGE


def _annotate_score(qs):
    return qs.annotate(
        score=Coalesce(Sum("votes__value"), 0),
        ups=Count("votes", filter=Q(votes__value=1)),
        downs=Count("votes", filter=Q(votes__value=-1)),
    )


def _apply_comment_sort(qs, sort: str):
    # Every ordering ends with id so page boundaries stay deterministic on ties.
    if sort == "top":
        return qs.order_by("-score", "created_at", "id")
    if sort == "new":
        return qs.order_by("-created_at", "id")
    if sort == "old":
        return qs.order_by("created_at", "id")
    if sort == "controversial":
        # high engagement, near-zero score
        return qs.annotate(
            abs_score=Abs("score"),
            total_votes=F("ups") + F("downs"),
        ).order_by("abs_score", "-total_votes", "created_at", "id")
    # "best" (default): score-based with downvote penalty; falls back to created_at tiebreaker
    return qs.order_by("-score", "downs", "created_at", "id")


def notify_mentions(body: str, *, actor, target) -> None:
    for user in resolve_mentions(body, exclude_user=actor):
        notify(user, actor=actor, verb="mention", target=target)


class PostCommentListCreateView(WriteThrottleMixin, generics.ListCreateAPIView):
    serializer_class = CommentSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)
    pagination_class = CommentThreadPagination
    throttle_scope = "write"

    def get_post(self) -> Post:
        if not hasattr(self, "_post"):
            post = get_object_or_404(Post, pk=self.kwargs["pk"])
            if not post.is_approved and not can_see_unapproved(self.request.user, post):
                raise NotFound()
            self._post = post
        return self._post

    def get_queryset(self):
        qs = (
            _annotate_score(Comment.objects.filter(post=self.get_post()))
            .select_related("author")
            .prefetch_related("votes", "saves")
        )
        sort = self.request.query_params.get("sort", "best")
        return _apply_comment_sort(qs, sort)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["post"] = self.get_post()
        return ctx

    def perform_create(self, serializer):
        post = self.get_post()
        if post.deleted_at is not None or not post.is_approved:
            raise PermissionDenied("Comments are closed on this post.")
        if is_banned(self.request.user, post.community):
            raise PermissionDenied("You are banned from this community.")
        comment = serializer.save(author=self.request.user, post=post)
        community = post.community
        if comment.parent_id and comment.parent.author_id != self.request.user.id:
            notify(comment.parent.author, actor=self.request.user, verb="reply", target=comment)
        elif not comment.parent_id and comment.post.author_id != self.request.user.id:
            notify(
                comment.post.author,
                actor=self.request.user,
                verb="comment",
                target=comment,
                community=community,
            )
        notify_mentions(comment.body, actor=self.request.user, target=comment)


class UserCommentListView(generics.ListAPIView):
    """Public list of a user's (non-deleted) comments, newest first."""

    serializer_class = CommentSerializer
    permission_classes = (permissions.AllowAny,)

    def get_queryset(self):
        author = get_object_or_404(User, username__iexact=self.kwargs["username"])
        return (
            _annotate_score(
                Comment.objects.filter(
                    author=author,
                    deleted_at__isnull=True,
                    post__is_approved=True,
                    post__deleted_at__isnull=True,
                )
            )
            .select_related("author")
            .prefetch_related("votes", "saves")
            .order_by("-created_at")
        )


class CommentDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CommentSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly, IsAuthorOrModeratorForDelete)
    queryset = _annotate_score(
        Comment.objects.select_related("author").prefetch_related("votes", "saves")
    )

    def get_object(self):
        comment = super().get_object()
        post = comment.post
        if not post.is_approved and not can_see_unapproved(self.request.user, post):
            raise NotFound()
        return comment

    def perform_update(self, serializer):
        instance = serializer.instance
        if is_banned(self.request.user, instance.post.community):
            raise PermissionDenied("You are banned from this community.")
        if instance.deleted_at is not None:
            raise ValidationError("Deleted comments cannot be edited.")
        old_body = instance.body
        comment = serializer.save()
        if comment.body != old_body:
            CommentRevision.objects.create(
                comment=comment, body=old_body, edited_by=self.request.user
            )
            comment.edited_at = timezone.now()
            comment.save(update_fields=["edited_at"])
        notify_mentions(comment.body, actor=self.request.user, target=comment)

    def perform_destroy(self, instance):
        if instance.deleted_at is not None:
            return
        instance.deleted_at = timezone.now()
        instance.deleted_by = self.request.user
        instance.save(update_fields=["deleted_at", "deleted_by"])
        if instance.author_id != self.request.user.id:
            from apps.moderation.models import ModAction
            from apps.moderation.services import log_mod_action

            log_mod_action(
                instance.post.community,
                actor=self.request.user,
                action=ModAction.Action.COMMENT_REMOVE,
                target=instance,
            )
            notify(instance.author, actor=self.request.user, verb="mod_action", target=instance)


class CommentRevisionListView(generics.ListAPIView):
    serializer_class = CommentRevisionSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        comment = get_object_or_404(Comment, pk=self.kwargs["pk"])
        if comment.author_id != self.request.user.id and not is_moderator(
            self.request.user, comment.post.community
        ):
            raise PermissionDenied("Only the author or a moderator can view edit history.")
        return comment.revisions.select_related("edited_by")

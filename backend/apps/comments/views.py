from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions

from apps.notifications.services import notify
from apps.posts.models import Post
from apps.posts.permissions import IsAuthorOrModeratorForDelete

from .lib.mentions import resolve_mentions
from .models import Comment
from .serializers import CommentSerializer


def _annotate_score(qs):
    return qs.annotate(score=Coalesce(Sum("votes__value"), 0))


def notify_mentions(body: str, *, actor, target) -> None:
    for user in resolve_mentions(body, exclude_user=actor):
        notify(user, actor=actor, verb="mention", target=target)


class PostCommentListCreateView(generics.ListCreateAPIView):
    serializer_class = CommentSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

    def get_post(self) -> Post:
        if not hasattr(self, "_post"):
            self._post = get_object_or_404(Post, pk=self.kwargs["pk"])
        return self._post

    def get_queryset(self):
        return (
            _annotate_score(Comment.objects.filter(post=self.get_post()))
            .select_related("author")
            .order_by("created_at")
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["post"] = self.get_post()
        return ctx

    def perform_create(self, serializer):
        comment = serializer.save(author=self.request.user, post=self.get_post())
        community = comment.post.community
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


class CommentDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CommentSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly, IsAuthorOrModeratorForDelete)
    queryset = _annotate_score(Comment.objects.select_related("author"))

    def perform_update(self, serializer):
        comment = serializer.save()
        notify_mentions(comment.body, actor=self.request.user, target=comment)

    def perform_destroy(self, instance):
        if instance.deleted_at is not None:
            return
        instance.deleted_at = timezone.now()
        instance.deleted_by = self.request.user
        instance.save(update_fields=["deleted_at", "deleted_by"])
        if instance.author_id != self.request.user.id:
            notify(instance.author, actor=self.request.user, verb="mod_action", target=instance)

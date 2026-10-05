from rest_framework import generics, permissions, status
from rest_framework.response import Response

from apps.comments.models import Comment
from apps.comments.views import _annotate_score as _annotate_comment_score
from apps.common.throttling import WriteThrottleMixin
from apps.posts.models import Post
from apps.posts.views import _annotate_score as _annotate_post_score
from apps.posts.views import _base_post_qs

from .models import SavedItem
from .serializers import SavedItemSerializer, SaveRequestSerializer


def _load_targets(items) -> dict[tuple[str, int], object]:
    """Fetch saved posts/comments in two annotated queries instead of one bare GFK per row."""
    ids: dict[str, list[int]] = {"post": [], "comment": []}
    for item in items:
        ids[item.content_type.model].append(item.object_id)
    posts = _annotate_post_score(_base_post_qs(Post.objects.filter(pk__in=ids["post"])))
    # post/community: _is_hidden_from and can_see_unapproved read them for every saved comment.
    comments = _annotate_comment_score(
        Comment.objects.filter(pk__in=ids["comment"])
        .select_related("author", "post", "post__community")
        .prefetch_related("votes", "saves")
    )
    targets: dict[tuple[str, int], object] = {("post", p.pk): p for p in posts}
    targets.update({("comment", c.pk): c for c in comments})
    return targets


class SavedItemListCreateView(WriteThrottleMixin, generics.ListCreateAPIView):
    throttle_scope = "write"
    serializer_class = SavedItemSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        qs = SavedItem.objects.filter(user=self.request.user).select_related("content_type")
        type_filter = self.request.query_params.get("type")
        if type_filter in ("post", "comment"):
            qs = qs.filter(content_type__model=type_filter)
        return qs

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        context = {**self.get_serializer_context(), "targets": _load_targets(page)}
        return self.get_paginated_response(
            SavedItemSerializer(page, many=True, context=context).data
        )

    def create(self, request, *args, **kwargs):
        payload = SaveRequestSerializer(data=request.data, context={"request": request})
        payload.is_valid(raise_exception=True)
        ct = payload.validated_data["_content_type"]
        object_id = payload.validated_data["object_id"]

        existing = SavedItem.objects.filter(
            user=request.user, content_type=ct, object_id=object_id
        ).first()
        if existing is not None:
            existing.delete()
            return Response({"is_saved": False}, status=status.HTTP_200_OK)

        item = SavedItem.objects.create(user=request.user, content_type=ct, object_id=object_id)
        return Response(
            {
                "is_saved": True,
                "saved": SavedItemSerializer(item, context={"request": request}).data,
            },
            status=status.HTTP_201_CREATED,
        )

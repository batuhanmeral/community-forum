from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from apps.comments.serializers import CommentSerializer
from apps.posts.models import Post
from apps.posts.serializers import PostSerializer
from apps.posts.services import can_see_unapproved

from .models import SavedItem

ALLOWED_TARGETS = {"post", "comment"}


def _is_hidden_from(user, target) -> bool:
    post = target if isinstance(target, Post) else target.post
    return not post.is_approved and not can_see_unapproved(user, post)


class SaveRequestSerializer(serializers.Serializer):
    content_type = serializers.CharField()
    object_id = serializers.IntegerField(min_value=1)

    def validate_content_type(self, value: str) -> str:
        value = value.lower()
        if value not in ALLOWED_TARGETS:
            raise serializers.ValidationError(
                f"content_type must be one of {sorted(ALLOWED_TARGETS)}."
            )
        return value

    def validate(self, attrs):
        ct_name = attrs["content_type"]
        app_label = "posts" if ct_name == "post" else "comments"
        try:
            ct = ContentType.objects.get(app_label=app_label, model=ct_name)
        except ContentType.DoesNotExist as exc:
            raise serializers.ValidationError({"content_type": "Unknown content type."}) from exc
        model = ct.model_class()
        target = model.objects.filter(pk=attrs["object_id"]).first()
        user = self.context["request"].user
        already_saved = SavedItem.objects.filter(
            user=user, content_type=ct, object_id=attrs["object_id"]
        ).exists()
        # An existing save stays toggleable so a held post can still be un-saved.
        if target is None or (_is_hidden_from(user, target) and not already_saved):
            # Same error as a missing target so pending content's existence is not leaked.
            raise serializers.ValidationError({"object_id": "Target object not found."})
        attrs["_content_type"] = ct
        return attrs


class SavedItemSerializer(serializers.ModelSerializer):
    target_type = serializers.SerializerMethodField()
    target = serializers.SerializerMethodField()

    class Meta:
        model = SavedItem
        fields = ("id", "target_type", "object_id", "target", "created_at")
        read_only_fields = fields

    def get_target_type(self, obj: SavedItem) -> str:
        return obj.content_type.model

    def get_target(self, obj: SavedItem):
        targets = self.context.get("targets")
        # Without bulk-loaded targets (e.g. the create response) fall back to the GFK.
        if targets is None:
            target = obj.target
        else:
            target = targets.get((obj.content_type.model, obj.object_id))
        if target is None or _is_hidden_from(self.context["request"].user, target):
            return None
        ctx = self.context
        if obj.content_type.model == "post":
            return PostSerializer(target, context=ctx).data
        return CommentSerializer(target, context=ctx).data

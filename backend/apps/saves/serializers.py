from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from apps.comments.serializers import CommentSerializer
from apps.posts.serializers import PostSerializer

from .models import SavedItem

ALLOWED_TARGETS = {"post", "comment"}


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
        if not model.objects.filter(pk=attrs["object_id"]).exists():
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
        target = obj.target
        if target is None:
            return None
        ctx = self.context
        if obj.content_type.model == "post":
            return PostSerializer(target, context=ctx).data
        return CommentSerializer(target, context=ctx).data

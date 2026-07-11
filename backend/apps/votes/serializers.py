from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from .models import Vote

ALLOWED_TARGETS = {"post", "comment"}


class VoteRequestSerializer(serializers.Serializer):
    content_type = serializers.CharField(
        help_text="Lowercase model name: 'post' or 'comment'."
    )
    object_id = serializers.IntegerField(min_value=1)
    value = serializers.ChoiceField(choices=(-1, 1))

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
        attrs["_target"] = model.objects.get(pk=attrs["object_id"])
        return attrs


class VoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vote
        fields = ("id", "user", "content_type", "object_id", "value", "created_at")
        read_only_fields = fields

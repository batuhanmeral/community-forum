from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from apps.communities.models import Membership
from apps.posts.models import Post
from apps.posts.services import can_see_unapproved

from .models import ModAction, Report

ALLOWED_TARGETS = {"post", "comment", "user"}
_APP_FOR = {"post": "posts", "comment": "comments", "user": "users"}


class ReportCreateSerializer(serializers.Serializer):
    content_type = serializers.CharField()
    object_id = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=255)

    def validate_content_type(self, value: str) -> str:
        value = value.lower()
        if value not in ALLOWED_TARGETS:
            raise serializers.ValidationError(
                f"content_type must be one of {sorted(ALLOWED_TARGETS)}."
            )
        return value

    def validate(self, attrs):
        ct_name = attrs["content_type"]
        try:
            ct = ContentType.objects.get(app_label=_APP_FOR[ct_name], model=ct_name)
        except ContentType.DoesNotExist as exc:
            raise serializers.ValidationError({"content_type": "Unknown content type."}) from exc
        model = ct.model_class()
        target = model.objects.filter(pk=attrs["object_id"]).first()
        # A held post (or a comment on one) must look exactly like a missing target.
        if target is None or not self._is_visible(target):
            raise serializers.ValidationError({"object_id": "Target object not found."})
        attrs["_content_type"] = ct
        return attrs

    def _is_visible(self, target) -> bool:
        post = target if isinstance(target, Post) else getattr(target, "post", None)
        if post is None or post.is_approved:
            return True
        return can_see_unapproved(self.context["request"].user, post)


class ReportSerializer(serializers.ModelSerializer):
    target_type = serializers.SerializerMethodField()
    reporter_username = serializers.CharField(source="reporter.username", read_only=True)

    class Meta:
        model = Report
        fields = (
            "id",
            "reporter",
            "reporter_username",
            "target_type",
            "object_id",
            "reason",
            "status",
            "created_at",
        )
        read_only_fields = fields

    def get_target_type(self, obj: Report) -> str:
        return obj.content_type.model


class ModActionSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source="actor.username", read_only=True, default=None)
    target_type = serializers.SerializerMethodField()

    class Meta:
        model = ModAction
        fields = (
            "id",
            "actor",
            "actor_username",
            "action",
            "target_type",
            "object_id",
            "detail",
            "created_at",
        )
        read_only_fields = fields

    def get_target_type(self, obj: ModAction) -> str | None:
        return obj.content_type.model if obj.content_type_id else None


class MembershipRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = ("id", "user", "community", "role", "is_banned", "joined_at")
        read_only_fields = ("id", "user", "community", "joined_at")

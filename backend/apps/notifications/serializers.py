from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source="actor.username", read_only=True, default=None)
    target_type = serializers.SerializerMethodField()
    target_id = serializers.IntegerField(read_only=True)
    link = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = (
            "id",
            "recipient",
            "actor",
            "actor_username",
            "verb",
            "target_type",
            "target_id",
            "link",
            "created_at",
            "read_at",
        )
        read_only_fields = fields

    def get_target_type(self, obj: Notification) -> str | None:
        return obj.target_ct.model if obj.target_ct_id else None

    def get_link(self, obj: Notification) -> str | None:
        target = obj.target
        if target is None:
            return None
        model = obj.target_ct.model
        if model == "post":
            return f"/posts/{target.pk}"
        if model == "comment":
            return f"/posts/{target.post_id}#comment-{target.pk}"
        if model == "message":
            return f"/messages/{target.conversation_id}"
        if model == "user":
            return f"/u/{target.username}"
        if model == "community":
            return f"/c/{target.slug}"
        return None

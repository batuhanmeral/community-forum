from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source="actor.username", read_only=True, default=None)
    target_type = serializers.SerializerMethodField()
    target_id = serializers.IntegerField(read_only=True)

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
            "created_at",
            "read_at",
        )
        read_only_fields = fields

    def get_target_type(self, obj: Notification) -> str | None:
        return obj.target_ct.model if obj.target_ct_id else None

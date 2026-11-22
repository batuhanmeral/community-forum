from rest_framework import serializers

from .models import ModmailMessage, ModmailThread


def _name(user):
    return user.username if user is not None and user.is_active else None


class NewThreadSerializer(serializers.Serializer):
    subject = serializers.CharField(max_length=100)
    body = serializers.CharField(max_length=5000)


class NewMessageSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=5000)
    is_internal = serializers.BooleanField(required=False, default=False)


class ThreadUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=ModmailThread.Status.choices, required=False)
    assigned_to = serializers.IntegerField(required=False, allow_null=True, min_value=1)


class ThreadSerializer(serializers.ModelSerializer):
    """`context["moderator_view"]` adds assignment data; creators never see which mod is on it."""

    community = serializers.SlugRelatedField(read_only=True, slug_field="slug")
    creator_username = serializers.SerializerMethodField()
    unread = serializers.BooleanField(read_only=True, default=False)

    class Meta:
        model = ModmailThread
        fields = (
            "id",
            "community",
            "subject",
            "status",
            "creator_username",
            "unread",
            "created",
            "updated",
        )
        read_only_fields = fields

    def get_creator_username(self, obj):
        return _name(obj.creator)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if self.context.get("moderator_view"):
            data["assigned_to"] = instance.assigned_to_id
            data["assigned_to_username"] = _name(instance.assigned_to)
        return data


class MessageSerializer(serializers.ModelSerializer):
    author_username = serializers.SerializerMethodField()
    from_moderator = serializers.SerializerMethodField()

    class Meta:
        model = ModmailMessage
        fields = ("id", "author_username", "from_moderator", "body", "is_internal", "created")
        read_only_fields = fields

    def get_from_moderator(self, obj):
        return obj.author_id != obj.thread.creator_id

    def get_author_username(self, obj):
        # The creator sees "the mod team", not which moderator wrote a reply.
        if not self.context.get("moderator_view") and self.get_from_moderator(obj):
            return None
        return _name(obj.author)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self.context.get("moderator_view"):
            data.pop("is_internal")
        return data

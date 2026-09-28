from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Conversation, Message

User = get_user_model()

MESSAGE_BODY_MAX_CHARS = 5_000


class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.PrimaryKeyRelatedField(read_only=True)
    sender_username = serializers.CharField(source="sender.username", read_only=True)

    class Meta:
        model = Message
        fields = (
            "id",
            "conversation",
            "sender",
            "sender_username",
            "body",
            "created_at",
            "read_at",
        )
        read_only_fields = ("id", "conversation", "sender", "created_at", "read_at")
        extra_kwargs = {"body": {"max_length": MESSAGE_BODY_MAX_CHARS}}

    def validate_body(self, value: str) -> str:
        if not value or not value.strip():
            raise serializers.ValidationError("Body cannot be empty.")
        return value


class ConversationSerializer(serializers.ModelSerializer):
    participant_a = serializers.PrimaryKeyRelatedField(read_only=True)
    participant_b = serializers.PrimaryKeyRelatedField(read_only=True)
    other = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = (
            "id",
            "participant_a",
            "participant_b",
            "other",
            "last_message",
            "unread_count",
            "created_at",
        )
        read_only_fields = fields

    def _other_user(self, obj: Conversation):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        return obj.participant_b if obj.participant_a_id == request.user.id else obj.participant_a

    def get_other(self, obj: Conversation):
        user = self._other_user(obj)
        if not user:
            return None
        return {"id": user.id, "username": user.username}

    def get_last_message(self, obj: Conversation):
        msg = obj.messages.order_by("-created_at").first()
        return MessageSerializer(msg).data if msg else None

    def get_unread_count(self, obj: Conversation) -> int:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return 0
        return obj.messages.filter(read_at__isnull=True).exclude(sender=request.user).count()


class ConversationCreateSerializer(serializers.Serializer):
    username = serializers.CharField()

    def validate_username(self, value: str):
        request = self.context["request"]
        try:
            other = User.objects.get(username__iexact=value)
        except User.DoesNotExist as exc:
            raise serializers.ValidationError("User not found.") from exc
        if other.id == request.user.id:
            raise serializers.ValidationError("Cannot start a conversation with yourself.")
        from apps.social.models import is_blocked_between

        if is_blocked_between(request.user, other):
            raise serializers.ValidationError("You cannot message this user.")
        self._other = other
        return value

    def create(self, validated_data):
        request = self.context["request"]
        a, b = sorted((request.user, self._other), key=lambda u: u.id)
        conv, _ = Conversation.objects.get_or_create(participant_a=a, participant_b=b)
        return conv

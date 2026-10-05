from rest_framework import serializers

from .models import Community, CommunityRule, Flair, Membership
from .services import MOD_ROLES


class CommunitySerializer(serializers.ModelSerializer):
    creator = serializers.PrimaryKeyRelatedField(read_only=True)
    member_count = serializers.IntegerField(read_only=True)
    is_member = serializers.SerializerMethodField()
    my_role = serializers.SerializerMethodField()
    is_banned = serializers.SerializerMethodField()

    class Meta:
        model = Community
        fields = (
            "id",
            "slug",
            "name",
            "description",
            "avatar",
            "is_nsfw",
            "requires_approval",
            "creator",
            "created_at",
            "member_count",
            "is_member",
            "my_role",
            "is_banned",
            "banned_keywords",
        )
        read_only_fields = ("id", "creator", "created_at")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # AutoMod keywords are for active moderators only.
        m = self._membership(instance)
        if m is None or m.is_banned or m.role not in MOD_ROLES:
            data.pop("banned_keywords", None)
        return data

    def validate_slug(self, value: str) -> str:
        if self.instance is not None and value != self.instance.slug:
            raise serializers.ValidationError("Slug cannot be changed after creation.")
        return value

    def validate_avatar(self, value):
        if value is None:
            return value
        from apps.common.images import AVATAR_MAX_SIDE, downscale_image

        return downscale_image(value, AVATAR_MAX_SIDE)

    def _membership(self, obj: Community):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        return obj.memberships.filter(user=request.user).first()

    def get_is_member(self, obj: Community) -> bool:
        m = self._membership(obj)
        return m is not None and not m.is_banned

    def get_my_role(self, obj: Community) -> str | None:
        m = self._membership(obj)
        return m.role if m is not None and not m.is_banned else None

    def get_is_banned(self, obj: Community) -> bool:
        m = self._membership(obj)
        return m is not None and m.is_banned


class CommunityRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunityRule
        fields = ("id", "order", "short", "description", "created_at")
        read_only_fields = ("id", "created_at")


class FlairSerializer(serializers.ModelSerializer):
    color = serializers.RegexField(r"^#[0-9a-fA-F]{6}\Z", required=False)

    class Meta:
        model = Flair
        fields = ("id", "name", "color")
        read_only_fields = ("id",)


class MembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = ("id", "user", "community", "role", "notify_level", "joined_at")
        read_only_fields = ("id", "user", "community", "role", "joined_at")

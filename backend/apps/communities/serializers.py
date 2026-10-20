from rest_framework import serializers

from .models import HEX_COLOR_PATTERN, Community, CommunityRule, Flair, Membership
from .services import MOD_ROLES


class CommunitySerializer(serializers.ModelSerializer):
    creator = serializers.PrimaryKeyRelatedField(read_only=True)
    member_count = serializers.IntegerField(read_only=True)
    is_member = serializers.SerializerMethodField()
    my_role = serializers.SerializerMethodField()
    is_banned = serializers.SerializerMethodField()
    my_notify_level = serializers.SerializerMethodField()

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
            "my_notify_level",
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
        prefetched = getattr(obj, "my_memberships", None)
        if prefetched is not None:
            return prefetched[0] if prefetched else None
        # Every membership field reads this, so look it up once per community, not per field.
        cache = self.__dict__.setdefault("_membership_cache", {})
        if obj.pk not in cache:
            cache[obj.pk] = obj.memberships.filter(user=request.user).first()
        return cache[obj.pk]

    def get_is_member(self, obj: Community) -> bool:
        m = self._membership(obj)
        return m is not None and not m.is_banned

    def get_my_role(self, obj: Community) -> str | None:
        m = self._membership(obj)
        return m.role if m is not None and not m.is_banned else None

    def get_is_banned(self, obj: Community) -> bool:
        m = self._membership(obj)
        return m is not None and m.is_banned

    def get_my_notify_level(self, obj: Community) -> str | None:
        m = self._membership(obj)
        return m.notify_level if m is not None and not m.is_banned else None


class CommunityRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunityRule
        fields = ("id", "order", "short", "description", "created_at")
        read_only_fields = ("id", "created_at")


class FlairSerializer(serializers.ModelSerializer):
    color = serializers.RegexField(HEX_COLOR_PATTERN, required=False)

    class Meta:
        model = Flair
        fields = ("id", "name", "color")
        read_only_fields = ("id",)


class MembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = ("id", "user", "community", "role", "notify_level", "joined_at")
        read_only_fields = ("id", "user", "community", "role", "joined_at")

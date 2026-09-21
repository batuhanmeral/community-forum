from rest_framework import serializers

from .models import Community, CommunityRule, Flair, Membership


class CommunitySerializer(serializers.ModelSerializer):
    creator = serializers.PrimaryKeyRelatedField(read_only=True)
    member_count = serializers.IntegerField(read_only=True)
    is_member = serializers.SerializerMethodField()
    my_role = serializers.SerializerMethodField()

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
            "banned_keywords",
        )
        read_only_fields = ("id", "creator", "created_at")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # AutoMod keywords are mod-only; hide them from regular members/visitors.
        m = self._membership(instance)
        if m is None or m.role not in (Membership.Role.ADMIN, Membership.Role.MODERATOR):
            data.pop("banned_keywords", None)
        return data

    def validate_slug(self, value: str) -> str:
        if self.instance is not None and value != self.instance.slug:
            raise serializers.ValidationError("Slug cannot be changed after creation.")
        return value

    def _membership(self, obj: Community):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        return obj.memberships.filter(user=request.user).first()

    def get_is_member(self, obj: Community) -> bool:
        return self._membership(obj) is not None

    def get_my_role(self, obj: Community) -> str | None:
        m = self._membership(obj)
        return m.role if m else None


class CommunityRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunityRule
        fields = ("id", "order", "short", "description", "created_at")
        read_only_fields = ("id", "created_at")


class FlairSerializer(serializers.ModelSerializer):
    class Meta:
        model = Flair
        fields = ("id", "name", "color")
        read_only_fields = ("id",)


class MembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = ("id", "user", "community", "role", "notify_level", "joined_at")
        read_only_fields = ("id", "user", "community", "role", "joined_at")

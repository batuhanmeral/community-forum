from rest_framework import serializers

from .models import Community, CommunityRule, Membership


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
            "creator",
            "created_at",
            "member_count",
            "is_member",
            "my_role",
        )
        read_only_fields = ("id", "creator", "created_at")

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


class MembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = ("id", "user", "community", "role", "notify_level", "joined_at")
        read_only_fields = ("id", "user", "community", "role", "joined_at")

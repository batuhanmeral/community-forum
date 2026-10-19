from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class FollowUserSerializer(serializers.ModelSerializer):
    is_following = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "avatar", "is_following")
        read_only_fields = fields

    def get_is_following(self, obj) -> bool:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        follows = getattr(obj, "viewer_follows", None)
        if follows is not None:
            return follows
        return obj.followers.filter(follower=request.user).exists()

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    total_karma = serializers.SerializerMethodField()
    followers_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    is_following = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "email_verified",
            "avatar",
            "bio",
            "show_nsfw",
            "post_karma",
            "comment_karma",
            "total_karma",
            "followers_count",
            "following_count",
            "is_following",
            "date_joined",
        )
        read_only_fields = ("id", "email_verified", "post_karma", "comment_karma", "date_joined")

    def validate_avatar(self, value):
        if value is None:
            return value
        from apps.common.images import AVATAR_MAX_SIDE, downscale_image

        return downscale_image(value, AVATAR_MAX_SIDE)

    def get_total_karma(self, obj: User) -> int:
        return obj.post_karma + obj.comment_karma

    def get_followers_count(self, obj: User) -> int:
        return obj.followers.count()

    def get_following_count(self, obj: User) -> int:
        return obj.following.count()

    def get_is_following(self, obj: User) -> bool:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        if request.user.id == obj.id:
            return False
        return obj.followers.filter(follower=request.user).exists()


class PublicUserSerializer(UserSerializer):
    is_blocked = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        fields = tuple(
            f
            for f in UserSerializer.Meta.fields
            if f not in ("email", "email_verified", "show_nsfw")
        ) + ("is_blocked",)

    def get_is_blocked(self, obj: User) -> bool:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated or request.user.id == obj.id:
            return False
        return request.user.blocks.filter(blocked=obj).exists()


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_current_password(self, value: str) -> str:
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate_new_password(self, value: str) -> str:
        validate_password(value, user=self.context["request"].user)
        return value

    def save(self, **kwargs) -> User:
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = ("id", "username", "email", "password")
        read_only_fields = ("id",)

    def validate_username(self, value: str) -> str:
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value

    def validate_email(self, value: str) -> str:
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value

    def create(self, validated_data: dict) -> User:
        return User.objects.create_user(**validated_data)


class _UidTokenSerializer(serializers.Serializer):
    """Base for flows that carry a uid/token pair from an emailed link."""

    uid = serializers.CharField()
    token = serializers.CharField()

    def validate_uid(self, value: str) -> str:
        from django.utils.encoding import force_str
        from django.utils.http import urlsafe_base64_decode

        try:
            self._user = User.objects.get(pk=force_str(urlsafe_base64_decode(value)))
        except (User.DoesNotExist, ValueError, TypeError, OverflowError) as exc:
            raise serializers.ValidationError("Invalid link.") from exc
        return value


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(_UidTokenSerializer):
    new_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        from django.contrib.auth.tokens import default_token_generator

        if not default_token_generator.check_token(self._user, attrs["token"]):
            raise serializers.ValidationError({"token": "Invalid or expired link."})
        validate_password(attrs["new_password"], user=self._user)
        return attrs

    def save(self, **kwargs) -> User:
        self._user.set_password(self.validated_data["new_password"])
        self._user.save(update_fields=["password"])
        return self._user


class EmailVerifySerializer(_UidTokenSerializer):
    def validate(self, attrs):
        from .tokens import email_verification_token

        if not email_verification_token.check_token(self._user, attrs["token"]):
            raise serializers.ValidationError({"token": "Invalid or expired link."})
        return attrs

    def save(self, **kwargs) -> User:
        if not self._user.email_verified:
            self._user.email_verified = True
            self._user.save(update_fields=["email_verified"])
        return self._user

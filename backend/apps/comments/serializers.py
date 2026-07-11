from rest_framework import serializers

from .models import Comment


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.PrimaryKeyRelatedField(read_only=True)
    author_username = serializers.CharField(source="author.username", read_only=True)

    class Meta:
        model = Comment
        fields = (
            "id",
            "post",
            "author",
            "author_username",
            "parent",
            "body",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "post", "author", "created_at", "updated_at")

    def validate_parent(self, value):
        if value is None:
            return value
        post = self.context.get("post")
        if post and value.post_id != post.id:
            raise serializers.ValidationError("Parent comment belongs to a different post.")
        return value

    def validate_body(self, value: str) -> str:
        if not value or not value.strip():
            raise serializers.ValidationError("Body cannot be empty.")
        return value

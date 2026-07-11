from rest_framework import serializers

from .models import Comment


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.PrimaryKeyRelatedField(read_only=True)
    author_username = serializers.CharField(source="author.username", read_only=True)
    score = serializers.IntegerField(read_only=True, default=0)
    user_vote = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = (
            "id",
            "post",
            "author",
            "author_username",
            "parent",
            "body",
            "score",
            "user_vote",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "post", "author", "created_at", "updated_at")

    def get_user_vote(self, obj: Comment) -> int | None:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        vote = next(
            (v for v in obj.votes.all() if v.user_id == request.user.id), None
        )
        return vote.value if vote else None

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

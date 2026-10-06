from rest_framework import serializers

from .models import Comment, CommentRevision

COMMENT_BODY_MAX_CHARS = 10_000


def _is_mod_removal(obj: Comment) -> bool:
    return (
        obj.deleted_at is not None
        and obj.deleted_by_id is not None
        and obj.deleted_by_id != obj.author_id
    )


def _mask_body(obj: Comment) -> str:
    if obj.deleted_at is None:
        return obj.body
    return "[removed]" if _is_mod_removal(obj) else "[deleted]"


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    author_username = serializers.SerializerMethodField()
    score = serializers.IntegerField(read_only=True, default=0)
    user_vote = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()
    body = serializers.CharField(max_length=COMMENT_BODY_MAX_CHARS, trim_whitespace=False)
    body_html = serializers.SerializerMethodField()
    is_deleted = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = (
            "id",
            "post",
            "author",
            "author_username",
            "parent",
            "body",
            "body_html",
            "is_deleted",
            "score",
            "user_vote",
            "is_saved",
            "created_at",
            "updated_at",
            "edited_at",
        )
        read_only_fields = ("id", "post", "created_at", "updated_at", "edited_at")

    def get_author(self, obj: Comment):
        return None if obj.deleted_at is not None else obj.author_id

    def get_author_username(self, obj: Comment):
        return None if obj.deleted_at is not None else obj.author.username

    def get_body_html(self, obj: Comment) -> str:
        return obj.body_html if obj.deleted_at is None else f"<p>{_mask_body(obj)}</p>"

    def get_is_deleted(self, obj: Comment) -> bool:
        return obj.deleted_at is not None

    def get_is_saved(self, obj: Comment) -> bool:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return any(s.user_id == request.user.id for s in obj.saves.all())

    def get_user_vote(self, obj: Comment) -> int | None:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        vote = next((v for v in obj.votes.all() if v.user_id == request.user.id), None)
        return vote.value if vote else None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["body"] = _mask_body(instance)
        return data

    def validate(self, attrs):
        body = attrs.get("body")
        if body is not None and not body.strip():
            raise serializers.ValidationError({"body": "Body cannot be empty."})
        return attrs

    def validate_parent(self, value):
        if self.instance is not None:
            # Re-parenting an existing comment would let it jump threads.
            if value != self.instance.parent:
                raise serializers.ValidationError("Parent cannot be changed.")
            return value
        if value is None:
            return value
        if value.deleted_at is not None:
            raise serializers.ValidationError("You cannot reply to a deleted comment.")
        post = self.context.get("post")
        if post and value.post_id != post.id:
            raise serializers.ValidationError("Parent comment belongs to a different post.")
        return value


class CommentRevisionSerializer(serializers.ModelSerializer):
    edited_by_username = serializers.CharField(
        source="edited_by.username", read_only=True, default=None
    )

    class Meta:
        model = CommentRevision
        fields = ("id", "body", "edited_at", "edited_by", "edited_by_username")
        read_only_fields = fields

from PIL import Image, UnidentifiedImageError
from rest_framework import serializers

from apps.polls.serializers import PollCreateInputSerializer, PollSerializer

from .models import Post

MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


class PostSerializer(serializers.ModelSerializer):
    author = serializers.PrimaryKeyRelatedField(read_only=True)
    community = serializers.SlugRelatedField(read_only=True, slug_field="slug")
    score = serializers.IntegerField(read_only=True, default=0)
    user_vote = serializers.SerializerMethodField()
    poll = serializers.SerializerMethodField()
    # Write-only payload used when kind='poll'
    poll_input = PollCreateInputSerializer(write_only=True, required=False)

    class Meta:
        model = Post
        fields = (
            "id",
            "author",
            "community",
            "flair",
            "kind",
            "title",
            "body",
            "url",
            "image",
            "is_nsfw",
            "is_pinned",
            "score",
            "user_vote",
            "poll",
            "poll_input",
            "created_at",
        )
        read_only_fields = ("id", "author", "community", "is_pinned", "created_at")

    def get_poll(self, obj: Post):
        poll = getattr(obj, "poll", None)
        if poll is None:
            return None
        return PollSerializer(poll, context=self.context).data

    def get_user_vote(self, obj: Post) -> int | None:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        vote = next(
            (v for v in obj.votes.all() if v.user_id == request.user.id), None
        )
        return vote.value if vote else None

    def validate_image(self, value):
        if value is None:
            return value
        if value.size > MAX_IMAGE_BYTES:
            raise serializers.ValidationError("Image exceeds 5 MB limit.")
        try:
            img = Image.open(value)
            fmt = (img.format or "").upper()
        except (UnidentifiedImageError, OSError) as exc:
            raise serializers.ValidationError("Invalid image file.") from exc
        finally:
            value.seek(0)
        if fmt not in ALLOWED_IMAGE_FORMATS:
            raise serializers.ValidationError(f"Unsupported image format: {fmt}.")
        return value

    def validate_flair(self, value):
        if value is None:
            return value
        community = self.context.get("community") or (
            self.instance.community if self.instance else None
        )
        if community and value.community_id != community.id:
            raise serializers.ValidationError(
                "Flair does not belong to this community."
            )
        return value

    def validate(self, attrs):
        kind = attrs.get("kind") or (self.instance.kind if self.instance else Post.Kind.TEXT)
        if kind == Post.Kind.LINK and not (attrs.get("url") or (self.instance and self.instance.url)):
            raise serializers.ValidationError({"url": "URL is required for link posts."})
        if kind == Post.Kind.IMAGE and not (attrs.get("image") or (self.instance and self.instance.image)):
            raise serializers.ValidationError({"image": "Image is required for image posts."})
        if kind == Post.Kind.POLL and not self.instance and not attrs.get("poll_input"):
            raise serializers.ValidationError(
                {"poll_input": "Poll posts require 'poll_input' with options and closes_at."}
            )
        return attrs

    def create(self, validated_data):
        from apps.polls.models import Poll, PollOption

        poll_payload = validated_data.pop("poll_input", None)
        post = super().create(validated_data)
        if post.kind == Post.Kind.POLL and poll_payload:
            poll = Poll.objects.create(post=post, closes_at=poll_payload["closes_at"])
            PollOption.objects.bulk_create(
                [
                    PollOption(poll=poll, text=text, order=idx)
                    for idx, text in enumerate(poll_payload["options"])
                ]
            )
        return post

    def update(self, instance, validated_data):
        validated_data.pop("poll_input", None)
        return super().update(instance, validated_data)

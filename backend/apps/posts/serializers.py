from PIL import Image, UnidentifiedImageError
from rest_framework import serializers

from apps.common.viewer import viewer_saved, viewer_vote
from apps.communities.serializers import FlairSerializer
from apps.polls.serializers import PollCreateInputSerializer, PollSerializer

from .models import Post, PostRevision
from .services import effective_nsfw, effective_spoiler, root_available

MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
POST_BODY_MAX_CHARS = 40_000


def _is_mod_removal(obj) -> bool:
    return obj.deleted_at is not None and obj.deleted_by_id != obj.author_id


def _mask_body(obj) -> str:
    if obj.deleted_at is None:
        return obj.body
    return "[removed]" if _is_mod_removal(obj) else "[deleted]"


class PostSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    author_username = serializers.SerializerMethodField()
    author_flair = serializers.SerializerMethodField()
    community = serializers.SlugRelatedField(read_only=True, slug_field="slug")
    flair_detail = FlairSerializer(source="flair", read_only=True)
    score = serializers.IntegerField(read_only=True, default=0)
    comment_count = serializers.IntegerField(read_only=True, default=0)
    user_vote = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()
    body = serializers.CharField(
        required=False, allow_blank=True, max_length=POST_BODY_MAX_CHARS, trim_whitespace=False
    )
    body_html = serializers.SerializerMethodField()
    is_deleted = serializers.SerializerMethodField()
    poll = serializers.SerializerMethodField()
    # Write-only payload used when kind='poll'
    poll_input = PollCreateInputSerializer(write_only=True, required=False)
    crosspost_from = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = (
            "id",
            "author",
            "author_username",
            "author_flair",
            "community",
            "flair",
            "flair_detail",
            "kind",
            "title",
            "body",
            "body_html",
            "is_deleted",
            "url",
            "image",
            "is_nsfw",
            "is_spoiler",
            "is_question",
            "accepted_comment",
            "bounty_amount",
            "bounty_expires_at",
            "bounty_status",
            "crosspost_from",
            "is_pinned",
            "is_approved",
            "score",
            "comment_count",
            "user_vote",
            "is_saved",
            "poll",
            "poll_input",
            "created_at",
            "edited_at",
        )
        read_only_fields = (
            "id",
            "author",
            "community",
            "is_pinned",
            "is_approved",
            "accepted_comment",
            "bounty_amount",
            "bounty_expires_at",
            "bounty_status",
            "created_at",
            "edited_at",
        )

    def get_author(self, obj: Post):
        # A deleted account's id would let its whole history be regrouped under one pseudonym.
        if obj.deleted_at is not None or not obj.author.is_active:
            return None
        return obj.author_id

    def get_author_flair(self, obj):
        from apps.communities.services import author_flair_data

        return author_flair_data(obj, obj.community_id)

    def get_author_username(self, obj: Post):
        # Removed content and deleted accounts both show as "[deleted]".
        if obj.deleted_at is not None or not obj.author.is_active:
            return None
        return obj.author.username

    def get_body_html(self, obj: Post) -> str:
        return obj.body_html if obj.deleted_at is None else f"<p>{_mask_body(obj)}</p>"

    def get_crosspost_from(self, obj: Post):
        root = obj.crosspost_parent
        if root is None:
            return None
        if not root_available(root):
            return {"id": root.pk, "community": None, "is_deleted": True}
        return {"id": root.pk, "community": root.community.slug, "is_deleted": False}

    def get_is_deleted(self, obj: Post) -> bool:
        return obj.deleted_at is not None

    def get_is_saved(self, obj: Post) -> bool:
        request = self.context.get("request")
        return viewer_saved(obj, request.user) if request else False

    def get_poll(self, obj: Post):
        poll = getattr(obj, "poll", None)
        if poll is None:
            return None
        return PollSerializer(poll, context=self.context).data

    def get_user_vote(self, obj: Post) -> int | None:
        request = self.context.get("request")
        return viewer_vote(obj, request.user) if request else None

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
        from apps.common.images import POST_IMAGE_MAX_SIDE, downscale_image

        return downscale_image(value, POST_IMAGE_MAX_SIDE)

    def validate_flair(self, value):
        if value is None:
            return value
        community = self.context.get("community") or (
            self.instance.community if self.instance else None
        )
        if community and value.community_id != community.id:
            raise serializers.ValidationError("Flair does not belong to this community.")
        return value

    def _validate_update_fields(self, attrs):
        # Kind is immutable, so only the fields that belong to it may change.
        kind = self.instance.kind
        if "url" in attrs and kind != Post.Kind.LINK and attrs["url"]:
            raise serializers.ValidationError({"url": "URL is only allowed on link posts."})
        if "url" in attrs and kind == Post.Kind.LINK and not attrs["url"]:
            raise serializers.ValidationError({"url": "URL is required for link posts."})
        if attrs.get("image") and kind != Post.Kind.IMAGE:
            raise serializers.ValidationError({"image": "Image is only allowed on image posts."})
        if "poll_input" in attrs:
            raise serializers.ValidationError({"poll_input": "Polls cannot be edited."})
        if self.instance.crosspost_parent_id and {"body", "url", "image"} & set(attrs):
            raise serializers.ValidationError("A crosspost's content cannot be changed.")

    def validate(self, attrs):
        if self.instance is not None:
            self._validate_update_fields(attrs)
        kind = attrs.get("kind") or (self.instance.kind if self.instance else Post.Kind.TEXT)
        is_question = attrs.get(
            "is_question", self.instance.is_question if self.instance else False
        )
        community = self.context.get("community") or (
            self.instance.community if self.instance else None
        )
        if is_question and (kind != Post.Kind.TEXT or (community and not community.qa_enabled)):
            raise serializers.ValidationError(
                {"is_question": "Questions require an enabled community and a text post."}
            )
        if (
            self.instance
            and "is_question" in attrs
            and attrs["is_question"] != self.instance.is_question
        ):
            raise serializers.ValidationError(
                {"is_question": "Question mode cannot be changed after posting."}
            )
        if kind == Post.Kind.LINK and not (
            attrs.get("url") or (self.instance and self.instance.url)
        ):
            raise serializers.ValidationError({"url": "URL is required for link posts."})
        if kind == Post.Kind.IMAGE and not (
            attrs.get("image") or (self.instance and self.instance.image)
        ):
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

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["body"] = _mask_body(instance)
        # Posts made before their community (or a crosspost's original) was flagged NSFW or
        # spoiler still carry the old flags.
        data["is_nsfw"] = effective_nsfw(instance)
        data["is_spoiler"] = effective_spoiler(instance)
        if instance.deleted_at is not None:
            # Removed content must not stay reachable through its link, media or poll.
            data.update(url="", image=None, poll=None)
        elif instance.crosspost_parent is not None and not root_available(
            instance.crosspost_parent
        ):
            # The copy was taken from a post that is gone or held; none of it may stay readable.
            data.update(
                title="[deleted]",
                body="[deleted]",
                body_html="<p>[deleted]</p>",
                url="",
                image=None,
                poll=None,
            )
        return data

    def validate_kind(self, value):
        if self.instance is not None and value != self.instance.kind:
            raise serializers.ValidationError("Post type cannot be changed after posting.")
        return value


class PostRevisionSerializer(serializers.ModelSerializer):
    edited_by_username = serializers.CharField(
        source="edited_by.username", read_only=True, default=None
    )

    class Meta:
        model = PostRevision
        fields = ("id", "title", "body", "edited_at", "edited_by", "edited_by_username")
        read_only_fields = fields

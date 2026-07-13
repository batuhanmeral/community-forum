from django.utils import timezone
from rest_framework import serializers

from .models import Poll, PollOption


class PollOptionSerializer(serializers.ModelSerializer):
    vote_count = serializers.IntegerField(read_only=True, default=0)
    percent = serializers.SerializerMethodField()

    class Meta:
        model = PollOption
        fields = ("id", "text", "order", "vote_count", "percent")
        read_only_fields = fields

    def get_percent(self, obj: PollOption) -> float:
        total = self.context.get("poll_total", 0)
        if not total:
            return 0.0
        return round((getattr(obj, "vote_count", 0) / total) * 100, 1)


class PollSerializer(serializers.ModelSerializer):
    options = serializers.SerializerMethodField()
    total_votes = serializers.SerializerMethodField()
    is_closed = serializers.SerializerMethodField()
    user_option = serializers.SerializerMethodField()

    class Meta:
        model = Poll
        fields = ("id", "closes_at", "is_closed", "total_votes", "user_option", "options")
        read_only_fields = fields

    def _options_with_counts(self, obj: Poll):
        if not hasattr(self, "_cached_options"):
            opts = list(obj.options.all())
            for o in opts:
                o.vote_count = o.votes.count()
            self._cached_options = opts
            self._total = sum(o.vote_count for o in opts)
        return self._cached_options

    def get_total_votes(self, obj: Poll) -> int:
        self._options_with_counts(obj)
        return self._total

    def get_options(self, obj: Poll):
        opts = self._options_with_counts(obj)
        ctx = {**self.context, "poll_total": self._total}
        return PollOptionSerializer(opts, many=True, context=ctx).data

    def get_is_closed(self, obj: Poll) -> bool:
        return obj.closes_at <= timezone.now()

    def get_user_option(self, obj: Poll) -> int | None:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        vote = obj.votes.filter(user=request.user).first()
        return vote.option_id if vote else None


class PollCreateInputSerializer(serializers.Serializer):
    """Used inside PostSerializer when kind='poll'."""

    closes_at = serializers.DateTimeField()
    options = serializers.ListField(
        child=serializers.CharField(max_length=200),
        min_length=2,
        max_length=10,
    )

    def validate_closes_at(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError("closes_at must be in the future.")
        return value


class PollVoteInputSerializer(serializers.Serializer):
    option_id = serializers.IntegerField(min_value=1)

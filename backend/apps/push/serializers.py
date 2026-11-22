from rest_framework import serializers

from .tasks import GROUPS
from .validators import validate_endpoint, validate_keys


class KeysSerializer(serializers.Serializer):
    p256dh = serializers.CharField(max_length=128)
    auth = serializers.CharField(max_length=64)


class SubscribeSerializer(serializers.Serializer):
    """The shape of `PushSubscription.toJSON()`."""

    endpoint = serializers.CharField(max_length=500)
    keys = KeysSerializer()

    def validate(self, attrs):
        try:
            attrs["endpoint"] = validate_endpoint(attrs["endpoint"])
            keys = attrs["keys"]
            attrs["p256dh"], attrs["auth"] = validate_keys(keys["p256dh"], keys["auth"])
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return attrs


class UnsubscribeSerializer(serializers.Serializer):
    endpoint = serializers.CharField(max_length=500)


class PreferenceSerializer(serializers.Serializer):
    enabled = serializers.BooleanField(required=False)
    types = serializers.DictField(child=serializers.BooleanField(), required=False)

    def validate_types(self, value):
        unknown = set(value) - set(GROUPS)
        if unknown:
            raise serializers.ValidationError(f"Unknown types: {sorted(unknown)}.")
        return value

from django.db import connection, transaction
from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.communities.services import is_banned
from apps.posts.services import can_see_unapproved

from .models import Vote
from .serializers import VoteRequestSerializer, VoteSerializer

# Namespace for the per-voter advisory lock (first key of pg_advisory_xact_lock).
VOTER_LOCK_NAMESPACE = 7001


def _lock_voter(user):
    # Advisory, not a row lock: a lock on the voter row would deadlock with the karma UPDATE.
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s, %s)", [VOTER_LOCK_NAMESPACE, user.pk])


class VoteView(APIView):
    """Upsert/toggle a vote. Same value → delete; different → update."""

    permission_classes = (permissions.IsAuthenticated,)
    throttle_scope = "vote"

    @transaction.atomic
    def post(self, request):
        _lock_voter(request.user)
        req = VoteRequestSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        ct = req.validated_data["_content_type"]
        object_id = req.validated_data["object_id"]
        value = req.validated_data["value"]
        target = req.validated_data["_target"]
        post = target if ct.model == "post" else target.post
        if not post.is_approved and not can_see_unapproved(request.user, post):
            # Held content must look identical to a missing target (no existence oracle).
            raise ValidationError({"object_id": ["Target object not found."]})
        if target.deleted_at is not None or post.deleted_at is not None or not post.is_approved:
            raise ValidationError("This content is no longer available for voting.")
        if is_banned(request.user, post.community):
            raise PermissionDenied("You are banned from this community.")

        existing = Vote.objects.filter(
            user=request.user, content_type=ct, object_id=object_id
        ).first()

        if existing is None:
            vote = Vote.objects.create(
                user=request.user, content_type=ct, object_id=object_id, value=value
            )
            return Response(
                {"user_vote": vote.value, "vote": VoteSerializer(vote).data},
                status=status.HTTP_201_CREATED,
            )

        if existing.value == value:
            existing.delete()
            return Response({"user_vote": None}, status=status.HTTP_200_OK)

        existing.value = value
        existing.save(update_fields=["value"])
        return Response(
            {"user_vote": existing.value, "vote": VoteSerializer(existing).data},
            status=status.HTTP_200_OK,
        )

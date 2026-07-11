from django.db import transaction
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Vote
from .serializers import VoteRequestSerializer, VoteSerializer


class VoteView(APIView):
    """Upsert/toggle a vote. Same value → delete; different → update."""

    permission_classes = (permissions.IsAuthenticated,)

    @transaction.atomic
    def post(self, request):
        req = VoteRequestSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        ct = req.validated_data["_content_type"]
        object_id = req.validated_data["object_id"]
        value = req.validated_data["value"]

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

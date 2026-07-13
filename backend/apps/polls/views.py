from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Poll, PollOption, PollVote
from .serializers import PollSerializer, PollVoteInputSerializer


class PollDetailView(APIView):
    permission_classes = (permissions.AllowAny,)

    def get(self, request, pk):
        poll = get_object_or_404(Poll, pk=pk)
        return Response(PollSerializer(poll, context={"request": request}).data)


class PollVoteView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @transaction.atomic
    def post(self, request, pk):
        poll = get_object_or_404(Poll, pk=pk)
        if poll.closes_at <= timezone.now():
            raise ValidationError("This poll is closed.")
        payload = PollVoteInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        option = PollOption.objects.filter(
            pk=payload.validated_data["option_id"], poll=poll
        ).first()
        if option is None:
            raise ValidationError({"option_id": "Option does not belong to this poll."})

        existing = PollVote.objects.select_for_update().filter(poll=poll, user=request.user).first()
        if existing is None:
            PollVote.objects.create(poll=poll, option=option, user=request.user)
            created = True
        elif existing.option_id != option.id:
            existing.option = option
            existing.save(update_fields=["option"])
            created = False
        else:
            created = False

        return Response(
            PollSerializer(poll, context={"request": request}).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

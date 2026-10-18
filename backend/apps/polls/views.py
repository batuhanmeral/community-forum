from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.communities.services import is_banned
from apps.posts.services import can_see_unapproved

from .models import Poll, PollOption, PollVote
from .serializers import PollSerializer, PollVoteInputSerializer
from .services import poll_prefetches


class PollDetailView(APIView):
    permission_classes = (permissions.AllowAny,)

    def get(self, request, pk):
        poll = get_object_or_404(
            Poll.objects.select_related("post__community").prefetch_related(
                *poll_prefetches(request.user)
            ),
            pk=pk,
        )
        hidden = poll.post.deleted_at is not None or (
            not poll.post.is_approved and not can_see_unapproved(request.user, poll.post)
        )
        if hidden:
            # Same 404 body a missing row gets, so the response can't confirm existence.
            get_object_or_404(Poll.objects.none(), pk=pk)
        return Response(PollSerializer(poll, context={"request": request}).data)


class PollVoteView(APIView):
    throttle_scope = "vote"
    permission_classes = (permissions.IsAuthenticated,)

    @transaction.atomic
    def post(self, request, pk):
        poll = get_object_or_404(Poll.objects.select_related("post__community"), pk=pk)
        if not poll.post.is_approved and not can_see_unapproved(request.user, poll.post):
            # An empty queryset yields the exact missing-poll 404, so held posts stay hidden.
            get_object_or_404(Poll.objects.none(), pk=pk)
        if poll.post.deleted_at is not None or not poll.post.is_approved:
            raise ValidationError("This poll is no longer available.")
        if is_banned(request.user, poll.post.community):
            raise PermissionDenied("You are banned from this community.")
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

        # Re-fetch so the prefetched counts and choice include the vote just written.
        poll = Poll.objects.prefetch_related(*poll_prefetches(request.user)).get(pk=poll.pk)
        return Response(
            PollSerializer(poll, context={"request": request}).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

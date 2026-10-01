from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.throttling import WriteThrottleMixin
from apps.notifications.services import notify

from .models import Conversation, Message
from .permissions import IsParticipant
from .serializers import (
    ConversationCreateSerializer,
    ConversationSerializer,
    MessageSerializer,
)


class ConversationListCreateView(WriteThrottleMixin, generics.ListCreateAPIView):
    throttle_scope = "write"
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        u = self.request.user
        return (
            Conversation.objects.filter(Q(participant_a=u) | Q(participant_b=u))
            .select_related("participant_a", "participant_b")
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        return (
            ConversationCreateSerializer
            if self.request.method == "POST"
            else ConversationSerializer
        )

    def create(self, request, *args, **kwargs):
        ser = ConversationCreateSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        conv = ser.save()
        out = ConversationSerializer(conv, context={"request": request})
        return Response(out.data, status=status.HTTP_201_CREATED)


class _ConversationScopedView:
    permission_classes = (permissions.IsAuthenticated, IsParticipant)

    def get_conversation(self) -> Conversation:
        if not hasattr(self, "_conv"):
            self._conv = get_object_or_404(Conversation, pk=self.kwargs["pk"])
            self.check_object_permissions(self.request, self._conv)
        return self._conv


class MessageListCreateView(
    WriteThrottleMixin, _ConversationScopedView, generics.ListCreateAPIView
):
    throttle_scope = "write"
    serializer_class = MessageSerializer

    def get_queryset(self):
        return (
            Message.objects.filter(conversation=self.get_conversation())
            .select_related("sender")
            .order_by("created_at")
        )

    def perform_create(self, serializer):
        from rest_framework.exceptions import PermissionDenied

        from apps.social.models import is_blocked_between

        conv = self.get_conversation()
        recipient = (
            conv.participant_b
            if conv.participant_a_id == self.request.user.id
            else conv.participant_a
        )
        if is_blocked_between(self.request.user, recipient):
            raise PermissionDenied("You cannot message this user.")
        msg = serializer.save(sender=self.request.user, conversation=conv)
        notify(recipient, actor=self.request.user, verb="dm", target=msg)


class ConversationReadView(_ConversationScopedView, APIView):
    def post(self, request, pk):
        conv = self.get_conversation()
        updated = (
            Message.objects.filter(conversation=conv, read_at__isnull=True)
            .exclude(sender=request.user)
            .update(read_at=timezone.now())
        )
        return Response({"marked_read": updated})

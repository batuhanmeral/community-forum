from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.throttling import WriteThrottleMixin
from apps.communities.models import Community
from apps.communities.services import is_moderator

from .models import ModmailThread
from .serializers import (
    MessageSerializer,
    NewMessageSerializer,
    NewThreadSerializer,
    ThreadSerializer,
    ThreadUpdateSerializer,
)
from .services import add_message, annotate_unread, create_thread, mark_read

User = get_user_model()


def _threads():
    return ModmailThread.objects.select_related("community", "creator", "assigned_to")


def _thread_for(user, pk: int) -> tuple[ModmailThread, bool]:
    """The thread and whether the user is a moderator of it; 404 for anyone uninvolved."""
    thread = get_object_or_404(_threads(), pk=pk)
    moderator = is_moderator(user, thread.community)
    if not moderator and thread.creator_id != user.pk:
        # Same 404 a missing thread gets, so the id cannot be probed.
        get_object_or_404(ModmailThread.objects.none(), pk=pk)
    return thread, moderator


class CommunityModmailView(WriteThrottleMixin, generics.ListCreateAPIView):
    """GET: the moderators' shared inbox. POST: any signed-in user opens a thread."""

    permission_classes = (permissions.IsAuthenticated,)
    throttle_scope = "write"

    def get_community(self):
        if not hasattr(self, "_community"):
            self._community = get_object_or_404(Community, slug=self.kwargs["slug"])
        return self._community

    def get_serializer_class(self):
        return NewThreadSerializer if self.request.method == "POST" else ThreadSerializer

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "moderator_view": True}

    def get_queryset(self):
        community = self.get_community()
        if not is_moderator(self.request.user, community):
            raise PermissionDenied("Only moderators can open the inbox.")
        wanted = self.request.query_params.get("status", ThreadSerializer.Meta.model.Status.OPEN)
        qs = _threads().filter(community=community, status=wanted)
        assigned = self.request.query_params.get("assigned")
        if assigned == "me":
            qs = qs.filter(assigned_to=self.request.user)
        elif assigned == "none":
            qs = qs.filter(assigned_to__isnull=True)
        return annotate_unread(qs, self.request.user, moderator_view=True)

    def create(self, request, *args, **kwargs):
        data = NewThreadSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        thread = create_thread(
            request.user,
            self.get_community(),
            data.validated_data["subject"],
            data.validated_data["body"],
        )
        thread = annotate_unread(
            _threads().filter(pk=thread.pk), request.user, moderator_view=False
        ).get()
        return Response(ThreadSerializer(thread).data, status=status.HTTP_201_CREATED)


class MyModmailView(generics.ListAPIView):
    serializer_class = ThreadSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        qs = _threads().filter(creator=self.request.user)
        return annotate_unread(qs, self.request.user, moderator_view=False)


class ModmailThreadView(WriteThrottleMixin, APIView):
    permission_classes = (permissions.IsAuthenticated,)
    throttle_scope = "write"

    def get(self, request, pk):
        thread, moderator = _thread_for(request.user, pk)
        thread = annotate_unread(
            _threads().filter(pk=thread.pk), request.user, moderator_view=moderator
        ).get()
        return Response(ThreadSerializer(thread, context={"moderator_view": moderator}).data)

    def patch(self, request, pk):
        thread, moderator = _thread_for(request.user, pk)
        if not moderator:
            raise PermissionDenied("Only moderators can change a thread.")
        data = ThreadUpdateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        if "assigned_to" in values:
            assignee_id = values["assigned_to"]
            if assignee_id is None:
                thread.assigned_to = None
            else:
                assignee = User.objects.filter(pk=assignee_id, is_active=True).first()
                if assignee is None or not is_moderator(assignee, thread.community):
                    raise ValidationError({"assigned_to": "Assignee must be a moderator."})
                thread.assigned_to = assignee
        if "status" in values:
            thread.status = values["status"]
        thread.save(update_fields=["assigned_to", "status", "updated"])
        return Response(ThreadSerializer(thread, context={"moderator_view": True}).data)


class ModmailMessagesView(WriteThrottleMixin, generics.ListCreateAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    throttle_scope = "write"

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.thread, self.moderator = _thread_for(request.user, kwargs["pk"])

    def get_serializer_class(self):
        return NewMessageSerializer if self.request.method == "POST" else MessageSerializer

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "moderator_view": self.moderator}

    def get_queryset(self):
        qs = self.thread.messages.select_related("author", "thread")
        return qs if self.moderator else qs.filter(is_internal=False)

    def create(self, request, *args, **kwargs):
        data = NewMessageSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        message = add_message(
            self.thread,
            request.user,
            data.validated_data["body"],
            internal=data.validated_data["is_internal"],
        )
        message = self.thread.messages.select_related("author", "thread").get(pk=message.pk)
        return Response(
            MessageSerializer(message, context={"moderator_view": self.moderator}).data,
            status=status.HTTP_201_CREATED,
        )


class ModmailReadView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, pk):
        thread, _ = _thread_for(request.user, pk)
        mark_read(thread, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

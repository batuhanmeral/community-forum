from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notifications.services import notify

from .models import Block, Follow, is_blocked_between
from .serializers import FollowUserSerializer

User = get_user_model()


def _get_target(username: str):
    return get_object_or_404(User, username__iexact=username)


class FollowToggleView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, username):
        target = _get_target(username)
        if target.id == request.user.id:
            raise ValidationError("You cannot follow yourself.")
        if is_blocked_between(request.user, target):
            raise ValidationError("You cannot follow this user.")
        follow, created = Follow.objects.get_or_create(follower=request.user, followed=target)
        if created:
            notify(target, actor=request.user, verb="follow", target=request.user)
        return Response(
            {"is_following": True},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request, username):
        target = _get_target(username)
        Follow.objects.filter(follower=request.user, followed=target).delete()
        return Response({"is_following": False})


class BlockToggleView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, username):
        target = _get_target(username)
        if target.id == request.user.id:
            raise ValidationError("You cannot block yourself.")
        _, created = Block.objects.get_or_create(blocker=request.user, blocked=target)
        if created:
            # Blocking severs the follow relationship in both directions.
            Follow.objects.filter(follower=request.user, followed=target).delete()
            Follow.objects.filter(follower=target, followed=request.user).delete()
        return Response(
            {"is_blocked": True},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request, username):
        target = _get_target(username)
        Block.objects.filter(blocker=request.user, blocked=target).delete()
        return Response({"is_blocked": False})


class BlockedListView(generics.ListAPIView):
    serializer_class = FollowUserSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return User.objects.filter(blocked_by__blocker=self.request.user).order_by(
            "-blocked_by__created_at"
        )


class FollowersListView(generics.ListAPIView):
    serializer_class = FollowUserSerializer
    permission_classes = (permissions.AllowAny,)

    def get_queryset(self):
        target = _get_target(self.kwargs["username"])
        return User.objects.filter(following__followed=target).order_by("-following__created_at")


class FollowingListView(generics.ListAPIView):
    serializer_class = FollowUserSerializer
    permission_classes = (permissions.AllowAny,)

    def get_queryset(self):
        target = _get_target(self.kwargs["username"])
        return User.objects.filter(followers__follower=target).order_by("-followers__created_at")

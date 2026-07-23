from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    ChangePasswordSerializer,
    PublicUserSerializer,
    RegisterSerializer,
    UserSerializer,
)

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = (permissions.AllowAny,)
    throttle_scope = "auth"


class MeView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = UserSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self):
        return self.request.user

    def perform_destroy(self, instance):
        # Deactivate instead of hard-deleting so authored content survives.
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class ChangePasswordView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    throttle_scope = "auth"

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserProfileView(generics.RetrieveAPIView):
    serializer_class = PublicUserSerializer
    permission_classes = (permissions.AllowAny,)
    lookup_field = "username__iexact"
    lookup_url_kwarg = "username"
    queryset = User.objects.filter(is_active=True)

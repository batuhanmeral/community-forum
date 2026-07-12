from django.contrib.auth import get_user_model
from rest_framework import generics, permissions

from .serializers import PublicUserSerializer, RegisterSerializer, UserSerializer

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = (permissions.AllowAny,)


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self):
        return self.request.user


class UserProfileView(generics.RetrieveAPIView):
    serializer_class = PublicUserSerializer
    permission_classes = (permissions.AllowAny,)
    lookup_field = "username__iexact"
    lookup_url_kwarg = "username"
    queryset = User.objects.all()

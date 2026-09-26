from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework import filters, generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from .models import Community, Membership
from .permissions import IsCreatorOrReadOnly
from .serializers import (
    CommunityRuleSerializer,
    CommunitySerializer,
    FlairSerializer,
    MembershipSerializer,
)
from .services import is_moderator


def _require_mod(user, community):
    if not is_moderator(user, community):
        raise PermissionDenied("Moderator role required.")


class CommunityViewSet(viewsets.ModelViewSet):
    queryset = Community.objects.all().annotate(member_count=Count("memberships"))
    serializer_class = CommunitySerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly, IsCreatorOrReadOnly)
    lookup_field = "slug"
    filter_backends = (filters.SearchFilter, filters.OrderingFilter)
    search_fields = ("slug", "name", "description")
    ordering_fields = ("created_at", "name", "member_count")
    ordering = ("-created_at",)
    parser_classes = (JSONParser, FormParser, MultiPartParser)

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)

    @action(
        detail=True,
        methods=("post", "delete", "patch"),
        url_path="membership",
        permission_classes=(permissions.IsAuthenticated,),
    )
    def membership(self, request, slug=None):
        community = self.get_object()

        if request.method == "POST":
            if Membership.objects.filter(
                user=request.user, community=community, is_banned=True
            ).exists():
                raise ValidationError("You are banned from this community.")
            if community.creator_id == request.user.id:
                role = Membership.Role.ADMIN
            else:
                role = Membership.Role.MEMBER
            obj, created = Membership.objects.get_or_create(
                user=request.user,
                community=community,
                defaults={"role": role},
            )
            serializer = MembershipSerializer(obj)
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )

        if request.method == "DELETE":
            membership = Membership.objects.filter(user=request.user, community=community).first()
            if not membership:
                return Response(status=status.HTTP_204_NO_CONTENT)
            if community.creator_id == request.user.id:
                raise ValidationError("Creator cannot leave their own community.")
            membership.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        # PATCH — update notify_level
        try:
            membership = Membership.objects.get(user=request.user, community=community)
        except Membership.DoesNotExist as exc:
            raise ValidationError("You are not a member of this community.") from exc
        serializer = MembershipSerializer(membership, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class CommunityRuleListCreateView(generics.ListCreateAPIView):
    serializer_class = CommunityRuleSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

    def get_community(self) -> Community:
        return get_object_or_404(Community, slug=self.kwargs["slug"])

    def get_queryset(self):
        return self.get_community().rules.all()

    def perform_create(self, serializer):
        community = self.get_community()
        _require_mod(self.request.user, community)
        serializer.save(community=community)


class CommunityRuleDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CommunityRuleSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

    def get_community(self) -> Community:
        return get_object_or_404(Community, slug=self.kwargs["slug"])

    def get_queryset(self):
        return self.get_community().rules.all()

    def perform_update(self, serializer):
        _require_mod(self.request.user, self.get_community())
        serializer.save()

    def perform_destroy(self, instance):
        _require_mod(self.request.user, self.get_community())
        instance.delete()


class FlairListCreateView(generics.ListCreateAPIView):
    serializer_class = FlairSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)
    pagination_class = None

    def get_community(self) -> Community:
        return get_object_or_404(Community, slug=self.kwargs["slug"])

    def get_queryset(self):
        return self.get_community().flairs.order_by("name")

    def perform_create(self, serializer):
        community = self.get_community()
        _require_mod(self.request.user, community)
        serializer.save(community=community)


class FlairDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = FlairSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

    def get_community(self) -> Community:
        return get_object_or_404(Community, slug=self.kwargs["slug"])

    def get_queryset(self):
        return self.get_community().flairs.all()

    def perform_update(self, serializer):
        _require_mod(self.request.user, self.get_community())
        serializer.save()

    def perform_destroy(self, instance):
        _require_mod(self.request.user, self.get_community())
        instance.delete()

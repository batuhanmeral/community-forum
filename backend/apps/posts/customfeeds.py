"""Custom feeds: named lists of communities, rendered through the shared feed pipeline."""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Exists, OuterRef, Prefetch
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from rest_framework import generics, permissions, serializers
from rest_framework.exceptions import ValidationError

from apps.common.throttling import WriteThrottleMixin
from apps.communities.models import Community, Membership

from .feed import build_post_feed
from .models import CustomFeed, Post
from .serializers import PostSerializer

User = get_user_model()

MAX_FEEDS_PER_USER = 20
MAX_COMMUNITIES_PER_FEED = 50
NAME_MAX = 50


class CustomFeedSerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source="owner.username", read_only=True)
    communities = serializers.SlugRelatedField(
        many=True, slug_field="slug", queryset=Community.objects.all(), required=False
    )

    class Meta:
        model = CustomFeed
        fields = (
            "id",
            "name",
            "slug",
            "description",
            "is_public",
            "owner_username",
            "communities",
            "created",
        )
        read_only_fields = ("id", "slug", "created")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # A just-written feed has no ordered prefetch, so sort here for a stable answer.
        data["communities"] = sorted(data["communities"])
        return data

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Name is required.")
        return value

    def validate_communities(self, value):
        unique = list({community.pk: community for community in value}.values())
        if len(unique) > MAX_COMMUNITIES_PER_FEED:
            raise serializers.ValidationError(
                f"A feed can hold at most {MAX_COMMUNITIES_PER_FEED} communities."
            )
        return unique


def _unique_slug(owner, name: str) -> str:
    base = slugify(name)[:NAME_MAX].strip("-") or "feed"
    slug, n = base, 1
    while CustomFeed.objects.filter(owner=owner, slug=slug).exists():
        n += 1
        suffix = f"-{n}"
        slug = f"{base[: NAME_MAX - len(suffix)]}{suffix}"
    return slug


def _feed_queryset():
    return CustomFeed.objects.select_related("owner").prefetch_related(
        Prefetch("communities", queryset=Community.objects.order_by("slug"))
    )


class MyFeedsView(WriteThrottleMixin, generics.ListCreateAPIView):
    """The signed-in user's feeds; POST creates one."""

    serializer_class = CustomFeedSerializer
    permission_classes = (permissions.IsAuthenticated,)
    throttle_scope = "write"

    def get_queryset(self):
        return _feed_queryset().filter(owner=self.request.user)

    def perform_create(self, serializer):
        with transaction.atomic():
            # Lock the owner row so concurrent creates cannot pass the cap or take the same slug.
            User.objects.select_for_update().get(pk=self.request.user.pk)
            if CustomFeed.objects.filter(owner=self.request.user).count() >= MAX_FEEDS_PER_USER:
                raise ValidationError(f"You can have at most {MAX_FEEDS_PER_USER} custom feeds.")
            serializer.save(
                owner=self.request.user,
                slug=_unique_slug(self.request.user, serializer.validated_data["name"]),
            )


class UserFeedListView(generics.ListAPIView):
    """A user's feeds: all of them for the owner, only public ones for everybody else."""

    serializer_class = CustomFeedSerializer
    permission_classes = (permissions.AllowAny,)

    def get_queryset(self):
        owner = get_object_or_404(User, username__iexact=self.kwargs["username"], is_active=True)
        qs = _feed_queryset().filter(owner=owner)
        return qs if self.request.user == owner else qs.filter(is_public=True)


class IsFeedOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.method in permissions.SAFE_METHODS or obj.owner_id == request.user.id


def _visible_feed(request, username, slug) -> CustomFeed:
    """404 unless the viewer may see the feed, so a private feed's existence is not leaked."""
    owner = get_object_or_404(User, username__iexact=username, is_active=True)
    feed = get_object_or_404(_feed_queryset(), owner=owner, slug=slug)
    if not feed.is_public and request.user != owner:
        get_object_or_404(CustomFeed.objects.none(), pk=feed.pk)
    return feed


class UserFeedDetailView(WriteThrottleMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CustomFeedSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly, IsFeedOwnerOrReadOnly)
    throttle_scope = "write"

    def get_object(self):
        feed = _visible_feed(self.request, self.kwargs["username"], self.kwargs["slug"])
        self.check_object_permissions(self.request, feed)
        return feed


class UserFeedPostsView(generics.ListAPIView):
    serializer_class = PostSerializer
    permission_classes = (permissions.AllowAny,)

    def get_queryset(self):
        request = self.request
        feed = _visible_feed(request, self.kwargs["username"], self.kwargs["slug"])
        qs = Post.objects.filter(community__in=feed.communities.values("pk"))
        if request.user.is_authenticated:
            # Like Home, a community the viewer is banned from contributes nothing.
            banned = Membership.objects.filter(
                user=request.user, community=OuterRef("community_id"), is_banned=True
            )
            qs = qs.exclude(Exists(banned))
        return build_post_feed(request, qs, "new")

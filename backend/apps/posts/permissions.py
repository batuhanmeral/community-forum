from rest_framework import permissions

from apps.communities.models import Membership


def is_moderator(user, community) -> bool:
    if not user or not user.is_authenticated:
        return False
    return Membership.objects.filter(
        user=user,
        community=community,
        role__in=(Membership.Role.ADMIN, Membership.Role.MODERATOR),
    ).exists()


class IsAuthorOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.author_id == request.user.id


class IsCommunityMember(permissions.BasePermission):
    """Used at creation time; the view must expose `get_community()`."""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        if not request.user.is_authenticated:
            return False
        community = view.get_community()
        return Membership.objects.filter(
            user=request.user, community=community
        ).exists()


class IsCommunityModerator(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return is_moderator(request.user, obj.community)

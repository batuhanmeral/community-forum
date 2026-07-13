from rest_framework import permissions

from apps.communities.models import Membership


def _has_role(user, community, *roles) -> bool:
    if not user or not user.is_authenticated:
        return False
    return Membership.objects.filter(
        user=user, community=community, role__in=roles, is_banned=False
    ).exists()


class IsCommunityModerator(permissions.BasePermission):
    """View must expose `get_community()`."""

    def has_permission(self, request, view):
        community = view.get_community()
        return _has_role(
            request.user,
            community,
            Membership.Role.ADMIN,
            Membership.Role.MODERATOR,
        )


class IsCommunityAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        community = view.get_community()
        return _has_role(request.user, community, Membership.Role.ADMIN)

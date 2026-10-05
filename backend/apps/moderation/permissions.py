from rest_framework import permissions

from apps.communities.models import Membership
from apps.communities.services import MOD_ROLES, has_role


class IsCommunityModerator(permissions.BasePermission):
    """View must expose `get_community()`."""

    def has_permission(self, request, view):
        return has_role(request.user, view.get_community(), *MOD_ROLES)


class IsCommunityAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return has_role(request.user, view.get_community(), Membership.Role.ADMIN)

from rest_framework import permissions

from .services import can_delete_community, can_edit_community


class IsCreatorOrReadOnly(permissions.BasePermission):
    """Write access for active admins (delete: the creator only); read for anyone."""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.method == "DELETE":
            return can_delete_community(request.user, obj)
        return can_edit_community(request.user, obj)

from rest_framework import permissions


class IsCreatorOrReadOnly(permissions.BasePermission):
    """Write access for the community creator or admin-role members; read for anyone."""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if obj.creator_id == request.user.id:
            return True
        if request.method == "DELETE":
            return False
        from .models import Membership

        return Membership.objects.filter(
            user=request.user,
            community=obj,
            role=Membership.Role.ADMIN,
            is_banned=False,
        ).exists()

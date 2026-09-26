from rest_framework import permissions

from apps.communities.models import Membership
from apps.communities.services import is_moderator


class IsAuthorOrModeratorForDelete(permissions.BasePermission):
    """Author can edit & delete; community moderators can delete only."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if obj.author_id == request.user.id:
            return True
        community = getattr(obj, "community", None) or getattr(
            getattr(obj, "post", None), "community", None
        )
        if request.method == "DELETE" and community is not None:
            return is_moderator(request.user, community)
        return False


class IsCommunityMember(permissions.BasePermission):
    """Used at creation time; the view must expose `get_community()`."""

    message = "You must be an unbanned member of this community."

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        if not request.user.is_authenticated:
            return False
        community = view.get_community()
        return Membership.objects.filter(
            user=request.user, community=community, is_banned=False
        ).exists()

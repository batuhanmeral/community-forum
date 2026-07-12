from rest_framework import permissions


class IsParticipant(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        user_id = getattr(request.user, "id", None)
        return user_id in (obj.participant_a_id, obj.participant_b_id)

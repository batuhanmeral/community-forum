"""Community role checks shared by every app that gates on membership."""

from .models import Community, Membership

MOD_ROLES = (Membership.Role.ADMIN, Membership.Role.MODERATOR)
_ROLE_RANK = {
    Membership.Role.MEMBER: 0,
    Membership.Role.MODERATOR: 1,
    Membership.Role.ADMIN: 2,
}


def active_membership(user, community: Community) -> Membership | None:
    """The user's unbanned membership, or None for anonymous, non-member or banned users."""
    if not user or not user.is_authenticated:
        return None
    return Membership.objects.filter(user=user, community=community, is_banned=False).first()


def has_role(user, community: Community, *roles: str) -> bool:
    membership = active_membership(user, community)
    return membership is not None and membership.role in roles


def is_moderator(user, community: Community) -> bool:
    return has_role(user, community, *MOD_ROLES)


def is_banned(user, community: Community) -> bool:
    if not user or not user.is_authenticated:
        return False
    return Membership.objects.filter(user=user, community=community, is_banned=True).exists()


def can_assign_role(actor, community: Community, new_role: str) -> bool:
    """Mods may only hand out roles ranked below their own; the creator may assign any."""
    actor_membership = active_membership(actor, community)
    if actor_membership is None or actor_membership.role not in MOD_ROLES:
        return False
    if actor.id == community.creator_id:
        return True
    return _ROLE_RANK[new_role] < _ROLE_RANK[actor_membership.role]


def can_moderate_member(actor, target_user, community: Community) -> bool:
    """Mods act only on members ranked strictly below them; the creator outranks everyone."""
    if target_user.id == community.creator_id:
        return False
    actor_membership = active_membership(actor, community)
    if actor_membership is None or actor_membership.role not in MOD_ROLES:
        return False
    if actor.id == community.creator_id:
        return True
    target_role = (
        Membership.objects.filter(user=target_user, community=community)
        .values_list("role", flat=True)
        .first()
    ) or Membership.Role.MEMBER
    return _ROLE_RANK[actor_membership.role] > _ROLE_RANK[target_role]

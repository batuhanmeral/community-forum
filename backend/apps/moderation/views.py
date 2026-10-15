from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.communities.models import Community, Membership
from apps.communities.services import (
    can_assign_role,
    can_lift_ban,
    can_moderate_member,
    roles_below,
)
from apps.notifications.services import notify

from .models import ModAction, Report
from .permissions import IsCommunityAdmin, IsCommunityModerator
from .serializers import (
    BannedMemberSerializer,
    MembershipRoleSerializer,
    ModActionSerializer,
    ReportCreateSerializer,
    ReportSerializer,
)
from .services import log_mod_action

User = get_user_model()


def _report_target_user(report: Report):
    """Return the user a mod_action notification should go to, if applicable."""
    obj = report.target
    if obj is None:
        return None
    if report.content_type.model == "user":
        return obj
    return getattr(obj, "author", None)


class ReportCreateView(APIView):
    throttle_scope = "write"
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        payload = ReportCreateSerializer(data=request.data, context={"request": request})
        payload.is_valid(raise_exception=True)
        ct = payload.validated_data["_content_type"]
        object_id = payload.validated_data["object_id"]
        cutoff = timezone.now() - timedelta(hours=24)
        recent = Report.objects.filter(
            reporter=request.user,
            content_type=ct,
            object_id=object_id,
            created_at__gte=cutoff,
        ).exists()
        if recent:
            raise ValidationError("You already reported this target in the last 24 hours.")
        report = Report.objects.create(
            reporter=request.user,
            content_type=ct,
            object_id=object_id,
            reason=payload.validated_data["reason"],
        )
        return Response(ReportSerializer(report).data, status=status.HTTP_201_CREATED)


class _CommunityModView:
    permission_classes = (permissions.IsAuthenticated, IsCommunityModerator)

    def get_community(self) -> Community:
        if not hasattr(self, "_community"):
            self._community = get_object_or_404(Community, slug=self.kwargs["slug"])
        return self._community


class CommunityReportListView(_CommunityModView, generics.ListAPIView):
    serializer_class = ReportSerializer

    def get_queryset(self):
        from django.db.models import Q

        from apps.comments.models import Comment
        from apps.posts.models import Post

        community = self.get_community()
        post_ct = ContentType.objects.get(app_label="posts", model="post")
        comment_ct = ContentType.objects.get(app_label="comments", model="comment")
        post_ids = Post.objects.filter(community=community).values_list("id", flat=True)
        comment_ids = Comment.objects.filter(post__community=community).values_list("id", flat=True)
        qs = Report.objects.filter(
            Q(content_type=post_ct, object_id__in=post_ids)
            | Q(content_type=comment_ct, object_id__in=comment_ids)
        )
        if self.request.query_params.get("status") in ("open", "resolved", "dismissed"):
            qs = qs.filter(status=self.request.query_params["status"])
        return qs.select_related("content_type").prefetch_related("target").order_by("-created_at")


class _ReportActionView(_CommunityModView, APIView):
    """Shared scoping for resolve/dismiss endpoints."""

    new_status = ""

    def post(self, request, slug, pk):
        community = self.get_community()
        report = get_object_or_404(Report, pk=pk)
        # Ensure target is inside this community
        from apps.comments.models import Comment
        from apps.posts.models import Post

        target = report.target
        in_community = False
        if isinstance(target, Post) and target.community_id == community.id:
            in_community = True
        elif isinstance(target, Comment) and target.post.community_id == community.id:
            in_community = True
        if not in_community:
            raise NotFound("Report not found in this community.")
        report.status = self.new_status
        report.save(update_fields=["status"])
        log_mod_action(
            community,
            actor=request.user,
            action=(
                ModAction.Action.REPORT_RESOLVE
                if self.new_status == Report.Status.RESOLVED
                else ModAction.Action.REPORT_DISMISS
            ),
            target=target,
            detail=report.reason,
        )
        if self.new_status == Report.Status.RESOLVED:
            recipient = _report_target_user(report)
            notify(recipient, actor=request.user, verb="mod_action", target=target)
        return Response(ReportSerializer(report).data)


class ReportResolveView(_ReportActionView):
    new_status = Report.Status.RESOLVED


class ReportDismissView(_ReportActionView):
    new_status = Report.Status.DISMISSED


class CommunityBanListView(_CommunityModView, generics.ListAPIView):
    serializer_class = BannedMemberSerializer

    def get_queryset(self):
        return (
            Membership.objects.filter(community=self.get_community(), is_banned=True)
            .select_related("user", "banned_by")
            .order_by(F("banned_at").desc(nulls_last=True), "-id")
        )


class CommunityBanView(_CommunityModView, APIView):
    """POST → ban (set is_banned=True); DELETE → unban."""

    def _get_target(self, username):
        return get_object_or_404(User, username__iexact=username)

    def _find_membership(self, target, community):
        return Membership.objects.filter(user=target, community=community).first()

    def post(self, request, slug, username):
        community = self.get_community()
        target = self._get_target(username)
        if target.id == community.creator_id:
            raise ValidationError("Cannot ban the community creator.")
        if target.id == request.user.id:
            raise ValidationError("Cannot ban yourself.")
        if not can_moderate_member(request.user, target, community):
            raise PermissionDenied("You can only ban members ranked below you.")
        membership, _ = Membership.objects.get_or_create(user=target, community=community)
        # Conditional write: concurrent bans must not take the ban over or log twice.
        # The role filter keeps a member promoted since the rank check from being demoted.
        banned = Membership.objects.filter(
            pk=membership.pk, is_banned=False, role__in=roles_below(request.user, community)
        ).update(
            is_banned=True,
            role=Membership.Role.MEMBER,
            banned_by=request.user,
            banned_at=timezone.now(),
        )
        membership.refresh_from_db()
        if not banned and not membership.is_banned:
            raise PermissionDenied("You can only ban members ranked below you.")
        if banned:
            log_mod_action(
                community, actor=request.user, action=ModAction.Action.USER_BAN, target=target
            )
            notify(target, actor=request.user, verb="mod_action", target=community)
        return Response(MembershipRoleSerializer(membership).data, status=status.HTTP_200_OK)

    def delete(self, request, slug, username):
        community = self.get_community()
        target = self._get_target(username)
        if not can_moderate_member(request.user, target, community):
            raise PermissionDenied("You can only unban members ranked below you.")
        membership = self._find_membership(target, community)
        if membership and membership.is_banned:
            if not can_lift_ban(request.user, membership, community):
                raise PermissionDenied(
                    "Only a moderator ranked at least as high as the one who issued this ban "
                    "can lift it."
                )
            # Lift only the ban that was checked, not one re-issued since the read.
            lifted = Membership.objects.filter(
                pk=membership.pk, is_banned=True, banned_by_id=membership.banned_by_id
            ).update(is_banned=False, banned_by=None, banned_at=None)
            if lifted:
                log_mod_action(
                    community, actor=request.user, action=ModAction.Action.USER_UNBAN, target=target
                )
        return Response(status=status.HTTP_204_NO_CONTENT)


class MembershipRoleView(APIView):
    """Admin-only: PATCH the role of a member."""

    permission_classes = (permissions.IsAuthenticated, IsCommunityAdmin)

    def get_community(self) -> Community:
        if not hasattr(self, "_community"):
            self._community = get_object_or_404(Community, slug=self.kwargs["slug"])
        return self._community

    def patch(self, request, slug, username):
        community = self.get_community()
        target = get_object_or_404(User, username__iexact=username)
        membership = get_object_or_404(Membership, user=target, community=community)
        if membership.is_banned:
            raise ValidationError("Unban this member before changing their role.")
        new_role = request.data.get("role")
        if new_role not in {c[0] for c in Membership.Role.choices}:
            raise ValidationError({"role": "Invalid role."})
        if target.id == community.creator_id and new_role != Membership.Role.ADMIN:
            raise ValidationError({"role": "Cannot demote the community creator."})
        if not can_moderate_member(request.user, target, community):
            raise PermissionDenied("You can only change roles of members ranked below you.")
        if not can_assign_role(request.user, community, new_role):
            raise PermissionDenied("You can only assign roles ranked below your own.")
        membership.role = new_role
        membership.save(update_fields=["role"])
        log_mod_action(
            community,
            actor=request.user,
            action=ModAction.Action.ROLE_CHANGE,
            target=target,
            detail=f"role → {new_role}",
        )
        notify(target, actor=request.user, verb="mod_action", target=community)
        return Response(MembershipRoleSerializer(membership).data)


class ModLogView(_CommunityModView, generics.ListAPIView):
    """Paginated audit log of moderator actions in a community."""

    serializer_class = ModActionSerializer

    def get_queryset(self):
        return (
            ModAction.objects.filter(community=self.get_community())
            .select_related("actor", "content_type")
            .order_by("-created_at")
        )

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.communities.models import Community, Membership
from apps.notifications.services import notify

from .models import Report
from .permissions import IsCommunityAdmin, IsCommunityModerator
from .serializers import (
    MembershipRoleSerializer,
    ReportCreateSerializer,
    ReportSerializer,
)

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
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        payload = ReportCreateSerializer(data=request.data)
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
        return qs.select_related("reporter", "content_type").order_by("-created_at")


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
        if self.new_status == Report.Status.RESOLVED:
            recipient = _report_target_user(report)
            notify(recipient, actor=request.user, verb="mod_action", target=target)
        return Response(ReportSerializer(report).data)


class ReportResolveView(_ReportActionView):
    new_status = Report.Status.RESOLVED


class ReportDismissView(_ReportActionView):
    new_status = Report.Status.DISMISSED


class CommunityBanView(_CommunityModView, APIView):
    """POST → ban (set is_banned=True); DELETE → unban."""

    def _get_target(self, username):
        return get_object_or_404(User, username__iexact=username)

    def post(self, request, slug, username):
        community = self.get_community()
        target = self._get_target(username)
        if target.id == community.creator_id:
            raise ValidationError("Cannot ban the community creator.")
        if target.id == request.user.id:
            raise ValidationError("Cannot ban yourself.")
        membership, _ = Membership.objects.update_or_create(
            user=target,
            community=community,
            defaults={"is_banned": True, "role": Membership.Role.MEMBER},
        )
        notify(target, actor=request.user, verb="mod_action", target=community)
        return Response(MembershipRoleSerializer(membership).data, status=status.HTTP_200_OK)

    def delete(self, request, slug, username):
        community = self.get_community()
        target = self._get_target(username)
        membership = Membership.objects.filter(user=target, community=community).first()
        if membership and membership.is_banned:
            membership.is_banned = False
            membership.save(update_fields=["is_banned"])
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
        new_role = request.data.get("role")
        if new_role not in {c[0] for c in Membership.Role.choices}:
            raise ValidationError({"role": "Invalid role."})
        if target.id == community.creator_id and new_role != Membership.Role.ADMIN:
            raise ValidationError({"role": "Cannot demote the community creator."})
        membership.role = new_role
        membership.save(update_fields=["role"])
        notify(target, actor=request.user, verb="mod_action", target=community)
        return Response(MembershipRoleSerializer(membership).data)

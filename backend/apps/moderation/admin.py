from django.contrib import admin
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html

from .models import Report
from .serializers import ALLOWED_TARGETS


class TargetTypeFilter(admin.SimpleListFilter):
    title = "target type"
    parameter_name = "target_type"

    def lookups(self, request, model_admin):
        return [(name, name.capitalize()) for name in sorted(ALLOWED_TARGETS)]

    def queryset(self, request, queryset):
        if self.value() in ALLOWED_TARGETS:
            return queryset.filter(content_type__model=self.value())
        return queryset


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "reporter",
        "content_type",
        "object_id",
        "target_link",
        "status",
        "created_at",
    )
    list_filter = ("status", TargetTypeFilter)
    list_select_related = ("reporter", "content_type")
    search_fields = ("reason",)
    raw_id_fields = ("reporter",)

    @admin.display(description="target")
    def target_link(self, obj: Report) -> str:
        ct = obj.content_type
        try:
            url = reverse(f"admin:{ct.app_label}_{ct.model}_change", args=[obj.object_id])
        except NoReverseMatch:
            return "-"
        return format_html('<a href="{}">open</a>', url)

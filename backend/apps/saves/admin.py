from django.contrib import admin

from .models import SavedItem


@admin.register(SavedItem)
class SavedItemAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "content_type", "object_id", "created_at")
    list_filter = ("content_type",)
    raw_id_fields = ("user",)

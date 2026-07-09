from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "recipient", "actor", "verb", "created_at", "read_at")
    list_filter = ("verb",)
    raw_id_fields = ("recipient", "actor")

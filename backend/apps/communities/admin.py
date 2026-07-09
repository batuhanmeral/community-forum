from django.contrib import admin

from .models import Community, Flair, Membership


@admin.register(Community)
class CommunityAdmin(admin.ModelAdmin):
    list_display = ("slug", "name", "creator", "is_nsfw", "created_at")
    search_fields = ("slug", "name")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "community", "role", "notify_level", "joined_at")
    list_filter = ("role", "notify_level")
    search_fields = ("user__username", "community__slug")


@admin.register(Flair)
class FlairAdmin(admin.ModelAdmin):
    list_display = ("community", "name", "color")
    search_fields = ("name", "community__slug")

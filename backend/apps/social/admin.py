from django.contrib import admin

from .models import Block, Follow


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ("id", "follower", "followed", "created_at")
    raw_id_fields = ("follower", "followed")


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ("id", "blocker", "blocked", "created_at")
    raw_id_fields = ("blocker", "blocked")

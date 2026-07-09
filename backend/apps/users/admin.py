from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Profile", {"fields": ("avatar", "bio", "post_karma", "comment_karma")}),
    )
    list_display = ("username", "email", "post_karma", "comment_karma", "is_staff")

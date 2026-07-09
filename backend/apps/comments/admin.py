from django.contrib import admin

from .models import Comment


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "post", "author", "parent", "created_at")
    search_fields = ("author__username", "body")
    raw_id_fields = ("post", "author", "parent")

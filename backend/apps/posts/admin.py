from django.contrib import admin

from .models import Post


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "community", "kind", "is_pinned", "is_nsfw", "created_at")
    list_filter = ("kind", "is_pinned", "is_nsfw")
    search_fields = ("title", "author__username", "community__slug")
    raw_id_fields = ("author", "community", "flair")

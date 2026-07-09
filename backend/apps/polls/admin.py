from django.contrib import admin

from .models import Poll, PollOption, PollVote


class PollOptionInline(admin.TabularInline):
    model = PollOption
    extra = 0


@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    list_display = ("id", "post", "closes_at")
    inlines = [PollOptionInline]


@admin.register(PollVote)
class PollVoteAdmin(admin.ModelAdmin):
    list_display = ("id", "poll", "option", "user", "created_at")
    raw_id_fields = ("poll", "option", "user")

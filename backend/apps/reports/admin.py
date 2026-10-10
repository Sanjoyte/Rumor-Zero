from django.contrib import admin

from apps.reports.models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    """A read-only list of reports (ARCHITECTURE §8). Resolving them (Dismiss, the actions on a
    post) is Part 10's moderation services; nothing here edits a report. Viewing needs
    `reports.view_report`: only a superuser until Part 10 grants it to the moderators. The list
    never shows the details text (it is on the page of one report), and `__str__` never does."""

    list_display = ("post", "reporter", "reason", "status", "counts_toward_threshold", "created_at")
    list_filter = ("status", "reason", "counts_toward_threshold", "created_at")
    search_fields = ("reporter__username",)
    list_select_related = ("post", "reporter")
    show_full_result_count = False
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
